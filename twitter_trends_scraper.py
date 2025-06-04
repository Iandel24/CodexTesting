"""Minimal scraper for Twitter trends in Argentina.

The script retrieves trending topics from Trends24 and then looks up recent
tweets for each topic using the public Nitter front end via the ``r.jina.ai``
proxy.  It performs basic sentiment analysis with NLTK's VADER after translating
tweets to English when possible.  Results are summarized with a simple
frequency-based approach and shown in a tiny Tkinter UI.  No official Twitter
API keys are required.
"""

import requests
from bs4 import BeautifulSoup
import tkinter as tk
import re
from collections import Counter
import string
import asyncio
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk.corpus import stopwords
from googletrans import Translator
from concurrent.futures import ThreadPoolExecutor

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
# Initialize NLTK tools for simple AI sentiment and summarization
nltk.download('vader_lexicon', quiet=True)
nltk.download('stopwords', quiet=True)

SID = SentimentIntensityAnalyzer()
STOPWORDS = set(stopwords.words('spanish'))
TRANSLATOR = Translator()

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
    while i < len(lines) and len(tweets) < 30:
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

def sentiment_score(text: str) -> float:
    """Return a compound sentiment score using NLTK.

    googletrans 4.x exposes an async ``translate`` method, while 3.x uses a
    regular function.  This helper handles both cases and falls back to the
    original text if translation fails.
    """
    try:
        result = TRANSLATOR.translate(text, dest="en")
        if hasattr(result, "__await__"):
            result = asyncio.run(result)
        translated = result.text
    except Exception:
        translated = text
    return SID.polarity_scores(translated)["compound"]


def summarize_tweets(tweets, n=10):
    """Return a summary consisting of the *n* most representative tweets."""
    freq = Counter(
        word.strip(string.punctuation).lower()
        for t in tweets
        for word in t.split()
        if word.lower() not in STOPWORDS
    )
    scored = []
    for t in tweets:
        score = sum(
            freq[word.strip(string.punctuation).lower()]
            for word in t.split()
            if word.lower() not in STOPWORDS
        )
        scored.append((score, t))
    scored.sort(reverse=True)
    return '\n'.join(t for _, t in scored[:n])

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
        in_left = any(k in text_lower for k in LEFT_KEYWORDS)
        in_right = any(k in text_lower for k in RIGHT_KEYWORDS)
        if in_left:
            left_scores.append(score)
        if in_right:
            right_scores.append(score)
        if not in_left and not in_right:
            left_scores.append(score)
            right_scores.append(score)

    def average(lst):
        return sum(lst) / len(lst) if lst else 0.0

    summary = summarize_tweets(tweets, n=10)
    return {
        'topic': topic,
        'description': summary,
        'sentiment_left': round(average(left_scores), 3),
        'sentiment_right': round(average(right_scores), 3)
    }

def build_ui(data):
    root = tk.Tk()
    root.title('Argentina Twitter Trends')

    text = tk.Text(root, wrap='word')
    scroll = tk.Scrollbar(root, command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    text.pack(side='left', fill='both', expand=True)
    scroll.pack(side='right', fill='y')

    for item in data:
        text.insert('end', f"Trend: {item['topic']}\n")
        text.insert('end', f"Description:\n{item['description']}\n")
        text.insert('end', f"Left sentiment: {item['sentiment_left']}\n")
        text.insert('end', f"Right sentiment: {item['sentiment_right']}\n")
        text.insert('end', '-' * 40 + '\n')

    text.configure(state='disabled')
    root.mainloop()

if __name__ == '__main__':
    topics = fetch_trending_topics()
    with ThreadPoolExecutor(max_workers=5) as ex:
        results = list(ex.map(analyze_trend, topics))
    build_ui(results)
