import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from pymongo import MongoClient
from datetime import datetime
from bson.objectid import ObjectId
import requests
import json
from werkzeug.utils import secure_filename

try:
    import google.generativeai as genai
except ImportError:
    genai = None

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configure Gemini if API key is present
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY and genai:
    genai.configure(api_key=GEMINI_API_KEY)

# Database Setup - Real MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client.ecosphere

users_collection = db.users
posts_collection = db.posts

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        # Basic mock authentication logic
        user = users_collection.find_one({'email': email})
        if user and user.get('password') == password: # In production, hash passwords!
            session['user_id'] = str(user['_id'])
            session['role'] = user['role']
            session['name'] = user['name']
            return redirect(url_for(f"{user['role']}_dashboard"))
        else:
            flash('Invalid email or password', 'error')
    return render_template('auth/login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role') # student, researcher, professional
        
        if users_collection.find_one({'email': email}):
            flash('Email already exists', 'error')
        else:
            user_id = users_collection.insert_one({
                'name': name,
                'email': email,
                'password': password, # MOCK ONLY
                'role': role,
                'preferences': {'theme': 'dark', 'language': 'en'}
            }).inserted_id
            
            session['user_id'] = str(user_id)
            session['role'] = role
            session['name'] = name
            return redirect(url_for(f"{role}_dashboard"))
            
    return render_template('auth/signup.html')

@app.route('/ask', methods=['POST'])
def ask_question():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    
    data = request.json
    category = data.get('category')
    question = data.get('question')
    
    if not category or not question:
        return {"error": "Missing fields"}, 400
    
    post_id = posts_collection.insert_one({
        'user_id': session['user_id'],
        'user_name': session['name'],
        'role': session['role'],
        'category': category,
        'content': question,
        'timestamp': datetime.now(),
        'type': 'question'
    }).inserted_id
    
    return {"message": "Question submitted successfully", "id": str(post_id)}, 200

@app.route('/api/connect', methods=['POST'])
def connect_user():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    
    name = request.form.get('name')
    role = request.form.get('role')
    target_user_id = request.form.get('targetUserId')
    
    file = request.files.get('resume')
    filepath = None
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
    
    db.connections.insert_one({
        'sender_id': session['user_id'],
        'sender_name': name,
        'sender_role': role,
        'target_user_id': target_user_id,
        'resume_path': filepath,
        'timestamp': datetime.now(),
        'status': 'pending'
    })
    
    return {"message": "Invitation sent successfully"}, 200

@app.route('/api/curiosity', methods=['POST'])
def curiosity_mode():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    
    data = request.json
    question = data.get('question')
    
    if not question:
        return {"error": "Missing question"}, 400

    prompt = f"""Your role is to transform a student's curiosity question into a structured research exploration.

The platform is used by students, researchers, and professionals to explore knowledge about:
- Healthcare
- Biology
- Ecosystems
- Plants
- Animals
- Emerging technologies

When a student asks a question, generate a response with the following structured sections.

RULES:
1. Explain concepts clearly for students.
2. Encourage curiosity and research thinking.
3. Avoid overly technical language.
4. Keep explanations concise but insightful.
5. Return the response strictly in JSON format.

OUTPUT FORMAT:

{{
  "biological_explanation": "Simple explanation of the concept.",
  "related_topics": [
    "Topic 1",
    "Topic 2",
    "Topic 3",
    "Topic 4"
  ],
  "research_questions": [
    "Question 1",
    "Question 2",
    "Question 3"
  ],
  "suggested_experiments": [
    "Experiment idea 1",
    "Experiment idea 2"
  ]
}}

Student Curiosity Question: {question}"""

    if GEMINI_API_KEY and genai:
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt)
            # Pluck out the JSON
            import re
            match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response.text, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                json_str = response.text
                
            result = json.loads(json_str)
            return result, 200
        except Exception as e:
            print(f"Gemini API Error: {e}")
            # Fallback deliberately passes to mock
            pass
            
    # Mock fallback
    return {
        "biological_explanation": f"This is a placeholder scientific explanation exploring the fundamentals of '{question}'. The concepts involve basic biological principles adapted for student understanding. (Mock Mode - No API Key)",
        "related_topics": ["Ecosystem Dynamics", "Cellular Biology", "Genetic Adaptation", "Environmental Factors"],
        "research_questions": [f"What is the primary driver behind {question}?", "How does this vary across different species?", "What role does the environment play?"],
        "suggested_experiments": ["Observe the reaction under a microscope using controlled variables.", "Set up a comparative study tracking growth rates in different lighting conditions."]
    }, 200

@app.route('/api/news')
def get_news():
    # Using arXiv API for Research Feed
    url = "http://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:physics+OR+cat:q-bio&sortBy=submittedDate&sortOrder=descending&max_results=10"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)
            
            ns = {'a': 'http://www.w3.org/2005/Atom'}
            formatted_news = []
            
            for entry in root.findall('a:entry', ns):
                title_elem = entry.find('a:title', ns)
                title = str(title_elem.text).strip().replace('\n', ' ') if title_elem is not None and title_elem.text else "No Title"
                
                summary_elem = entry.find('a:summary', ns)
                summary = str(summary_elem.text).strip().replace('\n', ' ') if summary_elem is not None and summary_elem.text else "No Description"
                
                published_elem = entry.find('a:published', ns)
                published = str(published_elem.text) if published_elem is not None and published_elem.text else ""
                
                # Extract links
                article_url = ""
                pdf_url = ""
                for link in entry.findall('a:link', ns):
                    href = str(link.attrib.get('href', ''))
                    rel = str(link.attrib.get('rel', ''))
                    title_attr = str(link.attrib.get('title', ''))
                    
                    if rel == 'alternate':
                        article_url = href
                    elif title_attr == 'pdf':
                        pdf_url = href
                
                if not pdf_url and article_url:
                    # Best effort fallback
                    pdf_url = article_url.replace('/abs/', '/pdf/')
                
                desc = str(summary)
                if len(desc) > 300:
                    desc = desc[:300] + "..."
                    
                # Real experiment/research generic images
                EXPERIMENT_IMAGES = [
                    "https://images.unsplash.com/photo-1532094349884-543bc11b234d?auto=format&fit=crop&w=600&q=80", # Microscope
                    "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=600&q=80", # Circuit board
                    "https://images.unsplash.com/photo-1581093458791-9f3c3900df4b?auto=format&fit=crop&w=600&q=80", # Lab vials
                    "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?auto=format&fit=crop&w=600&q=80", # Scientist
                    "https://images.unsplash.com/photo-1563207153-f404dc5f3969?auto=format&fit=crop&w=600&q=80", # Chemistry flasks
                    "https://images.unsplash.com/photo-1614935151651-0bea6508abb0?auto=format&fit=crop&w=600&q=80", # DNA
                    "https://images.unsplash.com/photo-1576086213369-97a306d36557?auto=format&fit=crop&w=600&q=80", # Petri dish
                    "https://images.unsplash.com/photo-1582719508461-905c673771fd?auto=format&fit=crop&w=600&q=80", # Research graph
                    "https://images.unsplash.com/photo-1574169208507-84376144848b?auto=format&fit=crop&w=600&q=80", # Pipettes
                    "https://images.unsplash.com/photo-1628595351029-c2bf17511435?auto=format&fit=crop&w=600&q=80"  # Robotics
                ]
                import hashlib
                image_idx = int(hashlib.md5(title.encode('utf-8')).hexdigest(), 16) % len(EXPERIMENT_IMAGES)
                selected_image = EXPERIMENT_IMAGES[image_idx]
                    
                formatted_news.append({
                    'title': title,
                    'description': desc,
                    'url': article_url,
                    'source': 'arXiv API',
                    'publishedAt': published,
                    'has_pdf': True if pdf_url else False,
                    'pdf_url': pdf_url,
                    'image': selected_image
                })
            return {"articles": formatted_news}, 200
    except Exception as e:
        print(f"arXiv API error: {e}")
            
    # Fallback mock data with PDF proofs as requested
    mock_news = [
        {
            'title': 'Breakthrough in Biodegradable Polymers',
            'description': 'Researchers have developed a new class of polymers that break down in marine environments within weeks.',
            'url': '#',
            'source': 'Nature Materials',
            'publishedAt': datetime.now().isoformat(),
            'has_pdf': True,
            'pdf_url': '#', # Would link to PDF
            'image': 'https://images.unsplash.com/photo-1532094349884-543bc11b234d?auto=format&fit=crop&w=400&q=80'
        },
        {
            'title': 'AI accelerates protein folding predictions',
            'description': 'A novel deep learning model has solved the structures of over 200 million proteins.',
            'url': '#',
            'source': 'Journal of Computational Biology',
            'publishedAt': datetime.now().isoformat(),
            'has_pdf': True,
            'pdf_url': '#',
            'image': 'https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=400&q=80'
        },
         {
            'title': 'Next-gen Solar Cells Hit 30% Efficiency',
            'description': 'Perovskite-silicon tandem solar cells have reached a new milestone in power conversion efficiency.',
            'url': '#',
            'source': 'Energy & Environmental Science',
            'publishedAt': datetime.now().isoformat(),
            'has_pdf': True,
            'pdf_url': '#',
            'image': 'https://images.unsplash.com/photo-1509391366360-1e97d5259d89?auto=format&fit=crop&w=400&q=80'
        }
    ]
    return {"articles": mock_news}, 200

# Dashboard routes with dynamic data
@app.route('/dashboard/student')
def student_dashboard():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
    # Fetch posts for the feed
    posts = list(posts_collection.find().sort('timestamp', -1))
    return render_template('dashboard/student.html', posts=posts)

@app.route('/dashboard/researcher')
def researcher_dashboard():
    if 'user_id' not in session or session.get('role') != 'researcher':
        return redirect(url_for('login'))
    # Fetch all student questions
    questions = list(posts_collection.find({'type': 'question'}).sort('timestamp', -1))
    return render_template('dashboard/researcher.html', questions=questions)

@app.route('/dashboard/professional')
def professional_dashboard():
    if 'user_id' not in session or session.get('role') != 'professional':
        return redirect(url_for('login'))
    # Professionals also see student questions to add practical insights
    questions = list(posts_collection.find({'type': 'question'}).sort('timestamp', -1))
    return render_template('dashboard/professional.html', questions=questions)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
