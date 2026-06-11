from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from googleapiclient.discovery import build
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import re
import os

# Serve the frontend folder as static files
# os.path.abspath ensures this resolves correctly in Vercel's serverless env
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)

analyzer = SentimentIntensityAnalyzer()

# ── helpers ──────────────────────────────────────────────────────────────────

def get_youtube_service(api_key: str):
    return build("youtube", "v3", developerKey=api_key)

def extract_video_id(url: str) -> str | None:
    """Extract video ID from any YouTube URL format."""
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11})",
        r"youtu\.be\/([0-9A-Za-z_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None

def extract_channel_id(url: str, yt) -> str | None:
    """Resolve channel URL to channel ID."""
    patterns = [
        r"youtube\.com\/channel\/([A-Za-z0-9_-]+)",
        r"youtube\.com\/@([A-Za-z0-9_.-]+)",
        r"youtube\.com\/c\/([A-Za-z0-9_-]+)",
        r"youtube\.com\/user\/([A-Za-z0-9_-]+)",
    ]
    for i, p in enumerate(patterns):
        m = re.search(p, url)
        if m:
            handle_or_id = m.group(1)
            if i == 0:          # already a channel ID
                return handle_or_id
            # resolve via search
            resp = yt.search().list(part="snippet", q=handle_or_id, type="channel", maxResults=1).execute()
            items = resp.get("items", [])
            if items:
                return items[0]["snippet"]["channelId"]
    return None

def fetch_channel_video_ids(yt, channel_id: str, max_videos: int = 10) -> list[str]:
    """Fetch recent video IDs for a channel."""
    video_ids = []
    page_token = None
    while len(video_ids) < max_videos:
        resp = yt.search().list(
            part="id",
            channelId=channel_id,
            maxResults=min(50, max_videos - len(video_ids)),
            type="video",
            order="date",
            pageToken=page_token,
        ).execute()
        for item in resp.get("items", []):
            video_ids.append(item["id"]["videoId"])
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return video_ids

def fetch_comments(yt, video_id: str, max_comments: int = 100) -> list[str]:
    """Fetch top-level comments for a video."""
    comments = []
    page_token = None
    while len(comments) < max_comments:
        try:
            resp = yt.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=min(100, max_comments - len(comments)),
                textFormat="plainText",
                pageToken=page_token,
            ).execute()
        except Exception:
            break
        for item in resp.get("items", []):
            text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
            comments.append(text)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return comments

def classify(compound: float) -> str:
    if compound >= 0.05:
        return "positive"
    elif compound <= -0.05:
        return "negative"
    return "neutral"

def analyse_comments(comments: list[str]) -> dict:
    """Run VADER on every comment and aggregate."""
    results = []
    pos = neg = neu = 0
    for c in comments:
        score = analyzer.polarity_scores(c)["compound"]
        label = classify(score)
        if label == "positive":
            pos += 1
        elif label == "negative":
            neg += 1
        else:
            neu += 1
        results.append({"text": c, "sentiment": label, "score": round(score, 3)})
    total = len(comments)
    return {
        "total": total,
        "positive": pos,
        "negative": neg,
        "neutral": neu,
        "pos_pct": round(pos / total * 100, 1) if total else 0,
        "neg_pct": round(neg / total * 100, 1) if total else 0,
        "neu_pct": round(neu / total * 100, 1) if total else 0,
        "comments": results,
    }

def generate_tips(stats: dict) -> list[str]:
    """Rule-based improvement suggestions for the channel owner."""
    tips = []
    pos_pct = stats["pos_pct"]
    neg_pct = stats["neg_pct"]
    total   = stats["total"]

    if pos_pct >= 70:
        tips.append("🌟 Your audience loves your content! Keep up the great work and maintain consistency.")
    elif pos_pct >= 50:
        tips.append("👍 Good positivity ratio. Focus on the topics that resonate most with viewers.")
    else:
        tips.append("⚠️ Your positivity ratio is below 50%. Consider re-evaluating your content strategy.")

    if neg_pct >= 30:
        tips.append("🔴 High negative comment ratio ({}%). Review the most-disliked comments for common themes and address them directly.".format(neg_pct))
    elif neg_pct >= 15:
        tips.append("🟡 Moderate negativity ({}%). Engage with criticism constructively in replies or a dedicated Q&A video.".format(neg_pct))
    else:
        tips.append("✅ Negative comments are low ({}%). Great community management!".format(neg_pct))

    if total < 50:
        tips.append("📢 Low comment volume. Encourage viewers with strong calls-to-action at the end of videos and ask open-ended questions.")
    elif total < 200:
        tips.append("📈 Growing engagement. Post consistently and collaborate with similar creators to boost comments.")
    else:
        tips.append("🚀 High comment volume! Pin a comment, create community posts, and use polls to deepen engagement.")

    tips.append("🎯 Reply to at least the top 10 comments on each video — it signals the algorithm and builds loyalty.")
    tips.append("🕐 Post videos when your audience is most active. Check YouTube Studio Analytics → Audience tab.")
    tips.append("🔔 Add an end-screen with subscription reminder and link to your most-commented video.")

    if neg_pct > pos_pct:
        tips.append("💡 Consider creating a 'Responding to Comments' video to address concerns publicly — it shows transparency and boosts trust.")

    return tips

# ── routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    body = request.get_json(force=True)
    api_key      = body.get("api_key", "").strip()
    url          = body.get("url", "").strip()
    max_comments = int(body.get("max_comments", 200))

    if not api_key:
        return jsonify({"error": "YouTube Data API key is required."}), 400
    if not url:
        return jsonify({"error": "YouTube URL is required."}), 400

    try:
        yt = get_youtube_service(api_key)

        # Determine if it's a video or channel URL
        video_id   = extract_video_id(url)
        channel_id = None if video_id else extract_channel_id(url, yt)

        if not video_id and not channel_id:
            return jsonify({"error": "Could not parse a valid YouTube video or channel URL."}), 400

        all_comments = []

        if video_id:
            # Single video
            all_comments = fetch_comments(yt, video_id, max_comments)
            source_type  = "video"
            source_id    = video_id
        else:
            # Channel — pull from up to 5 recent videos
            video_ids = fetch_channel_video_ids(yt, channel_id, max_videos=5)
            if not video_ids:
                return jsonify({"error": "No public videos found for this channel."}), 404
            per_video = max(20, max_comments // len(video_ids))
            for vid in video_ids:
                all_comments.extend(fetch_comments(yt, vid, per_video))
                if len(all_comments) >= max_comments:
                    break
            all_comments = all_comments[:max_comments]
            source_type  = "channel"
            source_id    = channel_id

        if not all_comments:
            return jsonify({"error": "No comments found. Comments may be disabled."}), 404

        stats = analyse_comments(all_comments)
        tips  = generate_tips(stats)

        return jsonify({
            "source_type": source_type,
            "source_id":   source_id,
            "stats":       stats,
            "tips":        tips,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
