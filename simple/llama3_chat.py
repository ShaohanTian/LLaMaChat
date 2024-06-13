from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import pymysql.cursors
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)


# Database connection settings
db_config = {
    'host': 'localhost',  # or the IP address of the MySQL server
    'port': 3306,
    'user': 'root',
    'password': '123456',
    'db': 'chat_app_db',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
}


def save_to_database(role, message):
    connection = pymysql.connect(**db_config)
    try:
        with connection.cursor() as cursor:
            sql = "INSERT INTO chat_history (role, message) VALUES (%s, %s)"
            cursor.execute(sql, (role, message))
        connection.commit()
    finally:
        connection.close()

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

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message')
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400
    save_to_database('User', user_message)


    response = gen_response(user_message)
    # print(f'**************** {user_message} ****************')
    # print(f'**************** {response} ****************')

    # Save user message and LLaMA-3 response to database
    save_to_database('LLaMA-3', response)

    return jsonify({'response': response})

if __name__=="__main__":

    app.run(debug=True)

