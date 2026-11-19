import json
import os
import sys
from google import genai
from google.genai import types
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOPICS_FILE = "topics.txt"


def get_next_topic():
    if not os.path.exists(TOPICS_FILE):
        return None, []
    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    if not lines:
        return None, []
    return lines[0], lines[1:]


def save_remaining_topics(remaining):
    with open(TOPICS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(remaining) + ("\n" if remaining else ""))


def generate_post(topic):
    client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"],
    http_options=types.HttpOptions(api_version="v1beta"),
)
    prompt = f"""
    Write a detailed, SEO-friendly blog post about: "{topic}".
    Return ONLY a JSON object with these exact keys:
    - "title": Catchy SEO title (under 65 characters)
    - "content": Clean HTML body using <h2>, <h3>, <p>, <ul>, <li> tags (no <html>, <body>, or <h1> tags)
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


def publish_to_blogger(post_data, is_draft=True):
    creds = Credentials(
        token=None,
        refresh_token=os.environ["BLOGGER_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["BLOGGER_CLIENT_ID"],
        client_secret=os.environ["BLOGGER_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/blogger"],
    )
    service = build("blogger", "v3", credentials=creds)

    body = {
        "kind": "blogger#post",
        "title": post_data["title"],
        "content": post_data["content"],
        "labels": post_data.get("labels", []),
    }
    result = service.posts().insert(
        blogId=os.environ["BLOG_ID"],
        body=body,
        isDraft=is_draft,
    ).execute()
    return result.get("url")


def main():
    topic, remaining = get_next_topic()
    if not topic:
        print("No topics left in topics.txt. Exiting.")
        sys.exit(0)

    print(f"Generating post for: {topic}")
    post_data = generate_post(topic)

    url = publish_to_blogger(post_data, is_draft=True)
    print(f"Created post: {post_data['title']} -> {url}")

    save_remaining_topics(remaining)


if __name__ == "__main__":
    main()
