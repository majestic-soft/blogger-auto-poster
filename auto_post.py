from datetime import datetime
import json
import os
import random
import urllib.parse
import urllib.request
from google import genai
from google.genai import types
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOPICS_FILE = "topics.txt"
HISTORY_FILE = "published_topics.txt"
CURRENT_YEAR = datetime.now().year
CURRENT_DATE = datetime.now().strftime("%B %Y")


def get_client():
    return genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options=types.HttpOptions(api_version="v1beta"),
    )


def load_lines(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def save_lines(filepath, lines):
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))


def generate_auto_topic(past_topics):
    client = get_client()
    avoid_list = "\n".join(f"- {t}" for t in past_topics[-50:]) if past_topics else "None yet"
    prompt = f"""
    Today's date is {CURRENT_DATE}.
    Suggest ONE specific, long-tail SEO blog topic for MajesticSoft (majesticsoft.in),
    a digital solutions partner offering Mobile App Development, Web Development,
    UI/UX Design, Digital Marketing, SEO/SMO, and BPO Services.

    Target Audience:
    - Strictly target startups, SMEs, and enterprise decision-makers in the US, UK, and EU.
    - Focus on high-intent international business questions: software/app development cost guides
      in USD/GBP/EUR, hiring dedicated offshore development teams, outsourcing BPO/customer support,
      or scaling digital marketing/SEO in Western markets.
    - NEVER generate India-local topics or mention Indian domestic pricing (INR).
    - Keep the topic relevant to {CURRENT_YEAR}. If you include a year, use {CURRENT_YEAR}.
      NEVER mention outdated years like 2023, 2024, or 2025.

    Do NOT repeat or closely duplicate any of these already published topics:
    {avoid_list}

    Return ONLY the topic title as a single plain-text line (no quotes, no numbering).
    """
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    return response.text.strip().strip('"')


def generate_post(topic):
    client = get_client()
    prompt = f"""
    Today's date is {CURRENT_DATE}. Write a detailed, SEO-friendly blog post for
    MajesticSoft (majesticsoft.in) about: "{topic}".

    Target Audience & Positioning:
    - Write directly for founders, CTOs, and marketing leaders in the US, UK, and European Union.
    - Use USD ($), GBP (£), or EUR (€) for any cost ranges or budget breakdowns—NEVER use INR.
    - Reference Western market standards where relevant (e.g., GDPR compliance, time-zone overlap,
      data security, and ROI benchmarks).
    - Position MajesticSoft as a cost-effective, reliable offshore digital solutions and BPO partner
      helping US, UK, and EU companies scale faster.

    Strict Rules:
    - Write from a {CURRENT_YEAR} perspective. Whenever mentioning the current year or latest trends, use {CURRENT_YEAR}.
    - NEVER refer to 2023, 2024, or 2025 as the current year.
    - Include practical insights, a concise HTML comparison or cost-breakdown <table> where helpful,
      and a short FAQ section at the end.
    - Include a brief, natural call-to-action at the end inviting US, UK, and EU businesses to
      discuss their project with MajesticSoft at https://www.majesticsoft.in/.

    Return ONLY a JSON object with these exact keys:
    - "title": Catchy SEO title (under 65 characters, using {CURRENT_YEAR} if a year is included)
    - "image_query": A simple 2 to 3 word stock photo search query directly matching the topic
      (e.g., "software development team", "digital marketing analytics", "modern corporate office", "customer support headset")
    - "content": Clean HTML body using <h2>, <h3>, <p>, <ul>, <li>, <table> tags
      (no <html>, <body>, or <h1> tags)
    - "labels": Array of 3 to 5 relevant Blogger category tags
    """
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )
    return json.loads(response.text)


def fetch_unsplash_image(query):
    access_key = os.environ["UNSPLASH_ACCESS_KEY"]
    for search_term in [query, "modern business technology"]:
        encoded = urllib.parse.quote(search_term)
        url = (
            f"https://api.unsplash.com/search/photos"
            f"?query={encoded}&orientation=landscape&per_page=8"
        )
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Client-ID {access_key}",
                "User-Agent": "Mozilla/5.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                results = data.get("results", [])
                if results:
                    chosen = random.choice(results[:5])
                    return chosen["urls"]["regular"]
        except Exception as e:
            print(f"Unsplash search failed for '{search_term}': {e}")
    return None


def build_featured_image_html(image_query, alt_text):
    image_url = fetch_unsplash_image(image_query)
    if not image_url:
        return ""
    safe_alt = alt_text.replace('"', "&quot;")
    return (
        f'<figure style="margin: 0 0 24px 0; text-align: center;">'
        f'<img src="{image_url}" alt="{safe_alt}" '
        f'style="width: 100%; max-width: 1200px; height: auto; border-radius: 10px; display: block; margin: 0 auto;" />'
        f'</figure>\n'
    )


def publish_to_blogger(post_data, is_draft=False):
    creds = Credentials(
        token=None,
        refresh_token=os.environ["BLOGGER_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["BLOGGER_CLIENT_ID"],
        client_secret=os.environ["BLOGGER_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/blogger"],
    )
    service = build("blogger", "v3", credentials=creds)

    image_html = build_featured_image_html(
        post_data.get("image_query", "modern business technology"),
        post_data["title"],
    )
    full_content = image_html + post_data["content"]

    body = {
        "kind": "blogger#post",
        "title": post_data["title"],
        "content": full_content,
        "labels": post_data.get("labels", []),
    }
    result = service.posts().insert(
        blogId=os.environ["BLOG_ID"],
        body=body,
        isDraft=is_draft,
    ).execute()
    return result.get("url")


def main():
    queued_topics = load_lines(TOPICS_FILE)
    past_topics = load_lines(HISTORY_FILE)

    if queued_topics:
        topic = queued_topics[0]
        remaining = queued_topics[1:]
        save_lines(TOPICS_FILE, remaining)
        print(f"Using queued topic: {topic}")
    else:
        topic = generate_auto_topic(past_topics)
        print(f"Auto-generated topic: {topic}")

    post_data = generate_post(topic)

    url = publish_to_blogger(post_data, is_draft=False)
    print(f"Published live with Unsplash image: {post_data['title']} -> {url}")

    past_topics.append(post_data["title"])
    save_lines(HISTORY_FILE, past_topics)


if __name__ == "__main__":
    main()
