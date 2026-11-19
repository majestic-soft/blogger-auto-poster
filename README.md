name: Auto Publish Blogger Post

on:
  schedule:
    - cron: "30 4 * * 1,4"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Generate and publish blog post
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          BLOGGER_CLIENT_ID: ${{ secrets.BLOGGER_CLIENT_ID }}
          BLOGGER_CLIENT_SECRET: ${{ secrets.BLOGGER_CLIENT_SECRET }}
          BLOGGER_REFRESH_TOKEN: ${{ secrets.BLOGGER_REFRESH_TOKEN }}
          BLOG_ID: ${{ secrets.BLOG_ID }}
        run: python auto_post.py

      - name: Update topics.txt
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add topics.txt
          git diff --staged --quiet || git commit -m "Remove published topic"
          git push
