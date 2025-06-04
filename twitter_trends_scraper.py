# Placeholder script for scraping Twitter trends for Argentina
# Requires network access and certain libraries like requests or bs4 which might
# not be present in this environment.

import json
import urllib.request
from html.parser import HTMLParser
import tkinter as tk
from tkinter import ttk

# A simple HTML parser to extract trending topics from trends24.in
class TrendsParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.trends = []
        self.in_link = False

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.in_link = True

    def handle_endtag(self, tag):
        if tag == 'a':
            self.in_link = False

    def handle_data(self, data):
        if self.in_link:
            text = data.strip()
            if text:
                self.trends.append(text)

# A very naive sentiment analyzer using small word lists
POSITIVE_WORDS = {
    "good", "great", "happy", "love", "excellent", "positive", "fortunate",
    "correct", "superior", "favorable"
}

NEGATIVE_WORDS = {
    "bad", "sad", "hate", "terrible", "awful", "negative", "unfortunate",
    "wrong", "inferior", "unfavorable"
}

def fetch_trending_topics():
    url = 'https://trends24.in/argentina/'
    try:
        with urllib.request.urlopen(url) as response:
            html = response.read().decode('utf-8', errors='ignore')
    except Exception:
        # Network is not available; return example data
        return ['TrendExample1', 'TrendExample2', 'TrendExample3']

    parser = TrendsParser()
    parser.feed(html)
    return parser.trends[:10]

def fetch_tweets_from_nitter(topic):
    search_url = f'https://nitter.net/search?f=tweets&q={urllib.parse.quote(topic)}'
    tweets = []
    try:
        with urllib.request.urlopen(search_url) as response:
            html = response.read().decode('utf-8', errors='ignore')
    except Exception:
        return tweets

    class TweetParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tweets = []
            self.capture = False

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == 'p' and attrs.get('class', '') == 'tweet-content media-body':
                self.capture = True

        def handle_endtag(self, tag):
            if tag == 'p' and self.capture:
                self.capture = False

        def handle_data(self, data):
            if self.capture:
                text = data.strip()
                if text:
                    self.tweets.append(text)

    parser = TweetParser()
    parser.feed(html)
    return parser.tweets[:10]

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
    left_accounts = {'@user_left_1', '@user_left_2'}
    right_accounts = {'@user_right_1', '@user_right_2'}

    left_scores = []
    right_scores = []
    for t in tweets:
        score = sentiment_score(t)
        # Placeholder logic: classify tweet by presence of left/right keywords
        if any(acc in t for acc in left_accounts):
            left_scores.append(score)
        elif any(acc in t for acc in right_accounts):
            right_scores.append(score)
        else:
            # Count toward both for neutrality
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

    tree = ttk.Treeview(root, columns=('Description', 'Left Sentiment', 'Right Sentiment'), show='headings')
    tree.heading('Description', text='Description (10 lines)')
    tree.heading('Left Sentiment', text='Left Wing Sentiment')
    tree.heading('Right Sentiment', text='Right Wing Sentiment')
    tree.pack(fill='both', expand=True)

    for item in data:
        tree.insert('', 'end', values=(item['description'], item['sentiment_left'], item['sentiment_right']))

    root.mainloop()

if __name__ == '__main__':
    topics = fetch_trending_topics()
    results = [analyze_trend(t) for t in topics]
    build_ui(results)
