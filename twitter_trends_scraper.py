"""Minimal scraper for Twitter trends in Argentina.

The script retrieves trending topics from Trends24 and then looks up recent
tweets for each topic using the public Nitter front end via the ``r.jina.ai``
proxy.  Sentiment is estimated with a naive positive/negative word list and
results are summarized by selecting representative tweets.  A tiny Tkinter UI
shows the data.  No Twitter API keys are required.

Before running the script make sure all dependencies are installed::

    pip install -r requirements.txt
"""

import sys

_missing = []
try:
    import requests
except Exception:
    _missing.append("requests")
try:
    from bs4 import BeautifulSoup
except Exception:
    _missing.append("beautifulsoup4")

if _missing:
    missing = ", ".join(_missing)
    sys.exit(
        f"Missing dependencies: {missing}. Install them with 'pip install -r requirements.txt'"
    )

import tkinter as tk
from tkinter import messagebox
from collections import Counter
import string
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

# Stopword list for simple summarization
STOPWORDS = {
    'de', 'la', 'que', 'el', 'en', 'y', 'a', 'los', 'del', 'se', 'las', 'por',
    'un', 'para', 'con', 'no', 'una', 'su', 'al', 'lo', 'como', 'más', 'pero',
    'sus', 'le', 'ya', 'o', 'este', 'sí', 'porque', 'esta', 'entre', 'cuando',
    'muy', 'sin', 'sobre', 'también', 'me', 'hasta', 'hay', 'donde', 'quien',
    'desde', 'todo', 'nos', 'durante', 'todos', 'uno', 'les', 'ni', 'contra'
}

# Word lists for naive sentiment scoring
POS_WORDS = {
    'bueno', 'buena', 'excelente', 'genial', 'feliz', 'fantástico', 'mejor',
    'amor', 'gracias', 'bien', 'increíble', 'apoyo', 'importante', 'fuerte',
    'grande', 'victoria', 'felicidades'
}
NEG_WORDS = {
    'malo', 'mala', 'terrible', 'horrible', 'odio', 'peor', 'triste',
    'corrupción', 'corrupcion', 'crisis', 'problema', 'fracaso', 'desastre',
    'mentira'
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

    # r.jina.ai renders the Nitter page as plain text where each tweet text
    # appears on its own line, followed by numeric statistics. There are no
    # timestamps, so we simply skip non-text lines and collect up to 30 entries.
    tweets = []
    for line in resp.text.splitlines():
        text = line.strip()
        if not text:
            continue
        if text.startswith("Title:") or text.startswith("URL Source:") or text.startswith("Markdown Content:"):
            continue
        if text.startswith("[") or text.startswith("!") or text == "GIF":
            continue
        stripped = text.replace(",", "").replace(".", "")
        if stripped.isdigit():
            continue
        tweets.append(text)
        if len(tweets) >= 30:
            break

    return tweets

def sentiment_score(text: str) -> float:
    """Return a naive sentiment score based on simple word lists."""
    words = [w.strip(string.punctuation).lower() for w in text.split()]
    score = 0
    for w in words:
        if w in POS_WORDS:
            score += 1
        if w in NEG_WORDS:
            score -= 1
    return score / len(words) if words else 0.0


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
    """Render the results in a minimal Tkinter UI with copy support.

    If a graphical display isn't available, print the data to stdout instead.
    """
    try:
        root = tk.Tk()
    except tk.TclError:
        for item in data:
            print(f"Trend: {item['topic']}")
            print(f"Description:\n{item['description']}")
            print(f"Left sentiment: {item['sentiment_left']}")
            print(f"Right sentiment: {item['sentiment_right']}")
            print('-' * 40)
        return

    root.title('Argentina Twitter Trends')

    frame = tk.Frame(root)
    frame.pack(fill='both', expand=True)

    text = tk.Text(frame, wrap='word')
    scroll = tk.Scrollbar(frame, command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    text.pack(side='left', fill='both', expand=True)
    scroll.pack(side='right', fill='y')

    for item in data:
        text.insert('end', f"Trend: {item['topic']}\n")
        text.insert('end', f"Description:\n{item['description']}\n")
        text.insert('end', f"Left sentiment: {item['sentiment_left']}\n")
        text.insert('end', f"Right sentiment: {item['sentiment_right']}\n")
        text.insert('end', '-' * 40 + '\n')

    def copy_all():
        root.clipboard_clear()
        root.clipboard_append(text.get('1.0', 'end'))
        messagebox.showinfo('Copy', 'Trends copied to clipboard')

    btn = tk.Button(root, text='Copy All', command=copy_all)
    btn.pack(fill='x')

    text.configure(state='disabled')
    root.mainloop()

if __name__ == '__main__':
    topics = fetch_trending_topics()
    with ThreadPoolExecutor(max_workers=5) as ex:
        results = list(ex.map(analyze_trend, topics))
    build_ui(results)
