from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import pymysql.cursors
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
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
    device_map="auto")

terminators = [
    tokenizer.eos_token_id,
    tokenizer.convert_tokens_to_ids("<|eot_id|>")]

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
        temperature=0.9,
        top_p=0.9,
        pad_token_id=128001
    )

    response = [tokenizer.decode(outputs[i][input_ids.shape[-1]:],
        skip_special_tokens=True) for i in range(outputs.shape[0])][0]
    return response


def gen_response_with_history(username, user_message):

    init_text = [
        # {"role": "system", "content": "Suppose you are a helpful assistant chat robot for human!"},
        {"role": "user", "content": user_message}
    ]
    # Tokenize the input and generate a response
    history_mes = get_user_chat_history(username)

    try:
        assert len(history_mes)>0
        input_text = history_mes + init_text
    except:
        input_text = [
        {"role": "system", "content": "Suppose you are a helpful assistant chat robot for human!"},
        {"role": "user", "content": user_message}
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
        temperature=0.9,
        top_p=0.95,
        pad_token_id=128001
    )

    response = [tokenizer.decode(outputs[i][input_ids.shape[-1]:],
        skip_special_tokens=True) for i in range(outputs.shape[0])][0]
    return response

def get_user_chat_history(username):
    connection = pymysql.connect(**db_config)
    try:
        with connection.cursor() as cursor:
            # Get user id from username
            sql = "SELECT id FROM users WHERE username = %s"
            cursor.execute(sql, (username,))
            user = cursor.fetchone()
            if not user:
                return None
            user_id = user['id']

            # Get chat history for the user, excluding created_at
            sql = """
                SELECT role, message AS content
                FROM chat_history
                WHERE user_id = %s
                ORDER BY created_at ASC
            """
            cursor.execute(sql, (user_id,))
            chat_history = cursor.fetchall()

            # Transform keys from 'message' to 'content'
            chat_history = [{'role': entry['role'], 'content': entry['content']} for entry in chat_history]

            return chat_history
    finally:
        connection.close()

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
                    user_id INT,
                    role VARCHAR(50),
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_archive (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    role VARCHAR(50),
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
        connection.commit()
    finally:
        connection.close()

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

def get_user_id(username):
    connection = pymysql.connect(**db_config)
    try:
        with connection.cursor() as cursor:
            sql = "SELECT id FROM users WHERE username = %s"
            cursor.execute(sql, (username,))
            user = cursor.fetchone()
            if user:
                return user['id']
    finally:
        connection.close()
    return None

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

def username_exists(username):
    connection = pymysql.connect(**db_config)
    try:
        with connection.cursor() as cursor:
            sql = "SELECT * FROM users WHERE username = %s"
            cursor.execute(sql, (username,))
            return cursor.fetchone() is not None
    finally:
        connection.close()

def save_to_database(username, role, message):
    user_id = get_user_id(username)
    if user_id is None:
        return False

    connection = pymysql.connect(**db_config)
    try:
        with connection.cursor() as cursor:
            sql = "INSERT INTO chat_history (user_id, role, message) VALUES (%s, %s, %s)"
            cursor.execute(sql, (user_id, role, message))
        with connection.cursor() as cursor:
            sql = "INSERT INTO chat_archive (user_id, role, message) VALUES (%s, %s, %s)"
            cursor.execute(sql, (user_id, role, message))
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

# @app.route('/register', methods=['GET', 'POST'])
# def register():
#     if request.method == 'POST':
#         username = request.form['username']
#         password = request.form['password']

#         if username_exists(username):
#             return jsonify({'success': False, 'message': 'Username already exists. Please choose a different username.'}), 400

#         save_user_to_database(username, password)
#         return redirect(url_for('login'))

#     return render_template('register.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Add validation if necessary
        # Validate username and password
        if not username or not password:
            return jsonify({'success': False, 'message': 'Username and password are required.'}), 400

        # Check if username already exists
        if username_exists(username):
            return jsonify({'success': False, 'message': 'Username already exists. Please choose a different username.'}), 400

        save_user_to_database(username, password)
        flash('Registration successful! Please log in.', 'success')
        return jsonify({'success': True, 'message': 'Registration successful! Redirecting to login...'}), 200

    return render_template('register.html')


@app.route('/logout', methods=['POST'])
def logout():
    if 'username' in session:
        session.pop('username', None)
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'User not logged in'}), 400

# @app.route('/chat')
# def chat():
#     if 'username' in session:
#         username = session['username']
#         return render_template('index.html', username=username)
#     else:
#         return redirect(url_for('login'))

@app.route('/chat')
def chat():
    if 'username' in session:
        username = session['username']
        chat_history = get_user_chat_history(username)
        return render_template('index.html', username=username, chat_history=chat_history)
    else:
        return redirect(url_for('login'))


@app.route('/chat', methods=['POST'])
def chat_message():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    username = session['username']
    user_message = request.json.get('message')
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400

    response = gen_response_with_history(username, user_message)
    # print(f'**************** {user_message} ****************')
    # print(f'**************** {response} ****************')
    save_to_database(username, 'user', user_message)
    save_to_database(username, 'system', response)


    return jsonify({'response': response})


@app.route('/clear', methods=['POST'])
def clear_chat_history():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    username = session['username']
    user_id = get_user_id(username)
    if user_id is None:
        return jsonify({'error': 'User not found'}), 404

    connection = pymysql.connect(**db_config)
    try:
        with connection.cursor() as cursor:
            sql = "DELETE FROM chat_history WHERE user_id = %s"
            cursor.execute(sql, (user_id,))
        connection.commit()
        return jsonify({'success': True})
    finally:
        connection.close()


if __name__ == "__main__":
    create_database_and_tables()
    app.run(debug=True)
