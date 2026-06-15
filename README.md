# Youtube-comment-analyzer
**YouTube Comment Analyzer** is an AI-powered application that analyzes comments from YouTube videos to understand audience opinions and feedback. It uses Natural Language Processing (NLP) and Machine Learning techniques to classify comments as positive, negative, or neutral. 
**YouTube Comment Analyzer** is an AI-powered application that collects comments from YouTube videos and performs sentiment analysis to understand audience opinions and feedback.

### Key Features

* 🔍 Fetch comments from any YouTube video using the YouTube Data API.
* 😊 Sentiment Analysis (Positive, Negative, Neutral).
* 📊 Visualize results using charts and graphs.
* ☁️ Store analyzed data in a database such as Supabase.
* 🤖 AI-generated insights and summaries.
* 🔑 Secure API key management using `.env` files.
* 📈 Comment statistics and engagement analysis.

### Tech Stack

* **Frontend:** Streamlit
* **Backend:** Python
* **AI/ML:** TextBlob, VADER, Transformers, or OpenAI API
* **Database:** Supabase
* **API:** YouTube Data API v3

### Working Flow

1. User enters a YouTube video URL.
2. System extracts the Video ID.
3. Comments are fetched using the YouTube Data API.
4. AI analyzes each comment's sentiment.
5. Results are stored and visualized.
6. Dashboard displays:

   * Total comments
   * Positive comments %
   * Negative comments %
   * Neutral comments %
   * AI-generated summary

