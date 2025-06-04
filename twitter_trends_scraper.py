"""Minimal scraper for Twitter trends in Argentina.

The script retrieves trending topics from Trends24 and then looks up recent
tweets for each topic using the public Nitter front end through a simple proxy
(`r.jina.ai`).  It performs a very naive sentiment analysis over the collected
tweets and displays everything in a Tkinter table.  No official Twitter API
keys are required.
"""

import requests
from bs4 import BeautifulSoup
import tkinter as tk
from tkinter import ttk
import re

# -------------------------------------------------------------
# Trend fetching
# -------------------------------------------------------------

def fetch_trending_topics():
    """Return the top 10 trending topics for Argentina."""
    url = "https://trends24.in/argentina/"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception:
        # Network unavailable - fall back to placeholder values
        return ["TrendExample1", "TrendExample2", "TrendExample3"]

    soup = BeautifulSoup(resp.text, "html.parser")
    card = soup.find("ol", class_="trend-card__list")
    if not card:
        return []
    return [li.get_text(strip=True) for li in card.find_all("li")][:10]

# A very naive sentiment analyzer using small word lists
POSITIVE_WORDS = {
    "good", "great", "happy", "love", "excellent", "positive", "fortunate",
    "correct", "superior", "favorable"
}

NEGATIVE_WORDS = {
    "bad", "sad", "hate", "terrible", "awful", "negative", "unfortunate",
    "wrong", "inferior", "unfavorable"
}

# Very small keyword sets to decide whether a tweet leans left or right.
LEFT_KEYWORDS = {"peronismo", "kirchnerismo", "izquierda"}
RIGHT_KEYWORDS = {"macri", "milei", "derecha", "liberal"}

def fetch_tweets_from_nitter(topic):
    """Retrieve up to 10 tweets for *topic* using Nitter via the r.jina.ai proxy."""
    encoded = requests.utils.quote(topic)
    search_url = f"https://r.jina.ai/https://nitter.net/search?f=tweets&q={encoded}"
    try:
        resp = requests.get(search_url, timeout=10)
        resp.raise_for_status()
    except Exception:
        return []

    # r.jina.ai returns the page as plain text/markdown. Tweets can be found
    # after lines that contain the timestamp (ending with 'UTC")'). The next
    # non-empty line following such a timestamp is the tweet text.
    lines = resp.text.splitlines()
    tweets = []
    timestamp_re = re.compile(r'UTC"\)$')

    i = 0
    while i < len(lines) and len(tweets) < 10:
        line = lines[i]
        if timestamp_re.search(line):
            j = i + 1
            # skip empty or numeric lines that sometimes appear after timestamps
            while j < len(lines) and (lines[j].strip() == "" or lines[j].strip().isdigit()):
                j += 1
            if j < len(lines):
                text_line = lines[j].strip()
                if text_line and not text_line.startswith("![") and not text_line.startswith("[]"):
                    tweets.append(text_line)
                i = j
        i += 1

    return tweets

def sentiment_score(text):
    words = {w.strip('.,!?:;').lower() for w in text.split()}
    pos = len(words & POSITIVE_WORDS)
    neg = len(words & NEGATIVE_WORDS)
    if pos + neg == 0:
        return 0.0
    return (pos - neg) / (pos + neg)

def analyze_trend(topic):
    tweets = fetch_tweets_from_nitter(topic)
    if not tweets:
        return {
            'topic': topic,
            'description': 'No data available',
            'sentiment_left': 0.0,
            'sentiment_right': 0.0
        }
    left_scores = []
    right_scores = []

    for t in tweets:
        score = sentiment_score(t)
        text_lower = t.lower()
        if any(k in text_lower for k in LEFT_KEYWORDS):
            left_scores.append(score)
        if any(k in text_lower for k in RIGHT_KEYWORDS):
            right_scores.append(score)
        if not (any(k in text_lower for k in LEFT_KEYWORDS) or any(k in text_lower for k in RIGHT_KEYWORDS)):
            # Neutral tweet contributes to both sides
            left_scores.append(score)
            right_scores.append(score)

    def average(lst):
        return sum(lst) / len(lst) if lst else 0.0

    return {
        'topic': topic,
        'description': '\n'.join(tweets[:10]),
        'sentiment_left': round(average(left_scores), 3),
        'sentiment_right': round(average(right_scores), 3)
    }

def build_ui(data):
    root = tk.Tk()
    root.title('Argentina Twitter Trends')

    tree = ttk.Treeview(
        root,
        columns=('Topic', 'Description', 'Left Sentiment', 'Right Sentiment'),
        show='headings'
    )
    tree.heading('Topic', text='Trend')
    tree.heading('Description', text='Description (10 lines)')
    tree.heading('Left Sentiment', text='Left Wing Sentiment')
    tree.heading('Right Sentiment', text='Right Wing Sentiment')
    tree.pack(fill='both', expand=True)

    for item in data:
        tree.insert(
            '',
            'end',
            values=(
                item['topic'],
                item['description'],
                item['sentiment_left'],
                item['sentiment_right']
            )
        )

    root.mainloop()

if __name__ == '__main__':
    topics = fetch_trending_topics()
    results = [analyze_trend(t) for t in topics]
    build_ui(results)
