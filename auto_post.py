from datetime import datetime
import json
import os
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
    a digital solutions company offering Mobile App Development, Web Development,
    UI/UX Design, Digital Marketing, SEO/SMO, and BPO Services.

    Focus on practical, high-intent business questions (comparisons, cost guides,
    how-to strategies) relevant to {CURRENT_YEAR}.
    If you include a year in the topic, use {CURRENT_YEAR}. NEVER mention outdated years like 2023, 2024, or 2025.

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

    Strict rules:
    - Write from a {CURRENT_YEAR} perspective. Whenever mentioning the current year or latest trends, use {CURRENT_YEAR}.
    - NEVER refer to 2023, 2024, or 2025 as the current year.
    - Include practical insights, a concise HTML comparison or summary <table> where helpful,
      and a short FAQ section at the end.
    - Include a brief, natural call-to-action at the end inviting readers to contact MajesticSoft
      at https://www.majesticsoft.in/ for their project.

    Return ONLY a JSON object with these exact keys:
    - "title": Catchy SEO title (under 65 characters, using {CURRENT_YEAR} if a year is included)
    - "image_prompt": A concise, clean English prompt for a modern, professional blog header
      illustration related to the topic (no text or words inside the image)
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


def build_featured_image_html(image_prompt, alt_text):
    encoded_prompt = urllib.parse.quote(image_prompt)
    image_url = (
        f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        "?width=1200&height=630&nologo=true"
    )

    try:
        req = urllib.request.Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=45):
            pass
    except Exception as e:
        print(f"Image pre-warm skipped: {e}")

    safe_alt = alt_text.replace('"', "&quot;")
    return (
        f'<figure style="margin: 0 0 24px 0; text-align: center;">'
        f'<img src="{image_url}" alt="{safe_alt}" '
        f'style="max-width: 100%; height: auto; border-radius: 8px;" loading="lazy" />'
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
        post_data.get("image_prompt", post_data["title"]),
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
    print(f"Published live with image: {post_data['title']} -> {url}")

    past_topics.append(post_data["title"])
    save_lines(HISTORY_FILE, past_topics)


if __name__ == "__main__":
    main()
