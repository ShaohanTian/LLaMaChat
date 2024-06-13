from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import pymysql.cursors
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = '123456'


# Database connection settings
db_config = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '123456',
    'db': 'chat_app_db',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
}


model_id = "D:/.cache/huggingface/hub/llama3-8b-instruct"
tokenizer = AutoTokenizer.from_pretrained(model_id)

# load model and tokenizer
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    torch_dtype=torch.bfloat16,
    device_map="auto",
)

terminators = [
    tokenizer.eos_token_id,
    tokenizer.convert_tokens_to_ids("<|eot_id|>")
]

if tokenizer.pad_token is None:
    tokenizer.add_special_tokens({'pad_token': '[PAD]'})
    model.resize_token_embeddings(len(tokenizer))

def gen_response(user_message):

    # Tokenize the input and generate a response
    input_text = [
        {"role": "system", "content": "Suppose you are a helpful assistant chat robot for human!"},
        {"role": "user", "content": user_message},
    ]

    input_ids = tokenizer.apply_chat_template(
        input_text,
        padding=True,
        add_generation_prompt=True,
        return_tensors="pt"
    ).to(model.device)

    outputs = model.generate(
        input_ids,
        max_new_tokens=4096,
        eos_token_id=terminators,
        do_sample=True,
        temperature=0.8,
        top_p=0.9,
        pad_token_id=128001
    )

    response = [tokenizer.decode(outputs[i][input_ids.shape[-1]:],
        skip_special_tokens=True) for i in range(outputs.shape[0])][0]
    return response

def create_database_and_tables():
    connection = pymysql.connect(**db_config)
    try:
        with connection.cursor() as cursor:
            cursor.execute("CREATE DATABASE IF NOT EXISTS chat_app_db")
            cursor.execute("USE chat_app_db")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255) NOT NULL UNIQUE,
                    password VARCHAR(255) NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    role VARCHAR(50),
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        connection.commit()
    finally:
        connection.close()

create_database_and_tables()

def save_user_to_database(username, password):
    hashed_password = generate_password_hash(password)
    connection = pymysql.connect(**db_config)
    try:
        with connection.cursor() as cursor:
            sql = "INSERT INTO users (username, password) VALUES (%s, %s)"
            cursor.execute(sql, (username, hashed_password))
        connection.commit()
    finally:
        connection.close()

# # Function to save user to database
# def save_user_to_database(username, password):
#     connection = pymysql.connect(**db_config)
#     try:
#         with connection.cursor() as cursor:
#             sql = "INSERT INTO users (username, password) VALUES (%s, %s)"
#             cursor.execute(sql, (username, password))
#         connection.commit()
#     finally:
#         connection.close()

# Insert a test user (run once, then comment out)
# save_user_to_database('testuser', 'testpassword')

def check_user(username, password):
    connection = pymysql.connect(**db_config)
    try:
        with connection.cursor() as cursor:
            sql = "SELECT * FROM users WHERE username = %s"
            cursor.execute(sql, (username,))
            user = cursor.fetchone()
            if user and check_password_hash(user['password'], password):
                return True
    finally:
        connection.close()
    return False

def save_to_database(role, message):
    connection = pymysql.connect(**db_config)
    try:
        with connection.cursor() as cursor:
            sql = "INSERT INTO chat_history (role, message) VALUES (%s, %s)"
            cursor.execute(sql, (role, message))
        connection.commit()
    finally:
        connection.close()

@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('chat'))
    else:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        if check_user(username, password):
            session['username'] = username
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Invalid credentials'})

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Add validation if necessary

        save_user_to_database(username, password)
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout', methods=['POST'])
def logout():
    if 'username' in session:
        session.pop('username', None)
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'User not logged in'}), 400


@app.route('/chat')
def chat():
    if 'username' in session:
        username = session['username']
        return render_template('index.html', username=username)
    else:
        return redirect(url_for('login'))

@app.route('/chat', methods=['POST'])
def chat_message():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user_message = request.json.get('message')
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400
    save_to_database('User', user_message)

    response = gen_response(user_message)
    print(f'**************** {user_message} ****************')
    print(f'**************** {response} ****************')
    save_to_database('LLaMA-3', response)

    return jsonify({'response': response})

if __name__ == "__main__":
    app.run(debug=True)
