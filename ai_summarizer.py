import os
from openai import OpenAI
from pymongo import MongoClient
import mongomock

# For local testing without a live MongoDB, we use mongomock
# In production, replace with a real MongoClient connection
client = mongomock.MongoClient()
db = client.ecosphere
posts_collection = db.posts
summaries_collection = db.summaries

def generate_feed_summary():
    """
    Fetches the latest trending topics/posts from the database and uses OpenAI 
    to generate a concise, platform-wide 'Knowledge Feed Summary' for the day.
    """
    
    # 1. Fetch recent posts (Mocking the query)
    # In a real app, this would be: posts = list(posts_collection.find().sort('timestamp', -1).limit(20))
    recent_posts = [
        {"type": "question", "content": "How does CRISPR minimize off-target effects?"},
        {"type": "insight", "content": "Telehealth adoption in rural areas is lower than expected due to connectivity."},
        {"type": "note", "content": "Epigenetic markers change significantly based on urban pollution exposure."}
    ]
    
    if not recent_posts:
        print("No recent posts found to summarize.")
        return None

    # 2. Prepare the prompt for OpenAI
    feed_content = "\n".join([f"- {post['type'].capitalize()}: {post['content']}" for post in recent_posts])
    
    prompt = f"""
    You are the AI assistant for EcoSphere, a curiosity-driven research learning platform.
    Below is a list of recent activities on the platform from students, researchers, and professionals.
    Please provide a short, engaging 2-paragraph summary highlighting the trending research themes of the day.

    Recent Activity:
    {feed_content}
    """

    # 3. Call OpenAI API
    # Note: Requires OPENAI_API_KEY environment variable to be set.
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("WARNING: OPENAI_API_KEY not found. Returning a mock summary.")
            return "Mock Summary: Today on EcoSphere, discussions heavily focus on genetic editing techniques like CRISPR and the impact of environmental factors on health, including urban pollution and telehealth challenges."
            
        openai_client = OpenAI(api_key=api_key)
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a scientific summarizer."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150
        )
        
        summary_text = response.choices[0].message.content.strip()
        
        # 4. Save summary back to database
        summary_doc = {
            "content": summary_text,
            "type": "daily_digest"
        }
        summaries_collection.insert_one(summary_doc)
        
        print("Successfully generated and saved new feed summary.")
        return summary_text
        
    except Exception as e:
        print(f"Error generating summary: {e}")
        return None

if __name__ == "__main__":
    print("Running AI Summarizer job...")
    result = generate_feed_summary()
    print(f"\nResult:\n{result}")
