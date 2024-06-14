// Check if marked is loaded before using it
if (window.marked) {
    initializeChat();
} else {
    document.querySelector('script[src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"]').addEventListener('load', initializeChat);
}

function initializeChat() {
    const chatBox = document.getElementById('chat-box');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const logoutButton = document.getElementById('logout-button');
    const copyButton = document.getElementById('copy-button');
    const clearButton = document.getElementById('clear-button');

    function getCurrentDateTime() {
        const now = new Date();
        const year = now.getFullYear();
        const month = (now.getMonth() + 1).toString().padStart(2, '0');
        const day = now.getDate().toString().padStart(2, '0');
        const hours = now.getHours().toString().padStart(2, '0');
        const minutes = now.getMinutes().toString().padStart(2, '0');
        const seconds = now.getSeconds().toString().padStart(2, '0');
        return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    }

    function addMessageToChatBox(message, role, isMarkdown = false) {
        const messageElement = document.createElement('div');
        messageElement.className = `message ${role.toLowerCase()}-message`;
        messageElement.innerHTML = isMarkdown ? window.marked.parse(message) : `${role}: ${message}`;
        
        const timeline = document.createElement('span');
        timeline.className = 'timeline';
        timeline.textContent = getCurrentDateTime();
        messageElement.appendChild(timeline);
        
        chatBox.appendChild(messageElement);
        chatBox.scrollTop = chatBox.scrollHeight;
        
        // Animate message entry
        setTimeout(() => {
            messageElement.style.opacity = 1;
            messageElement.style.transform = 'translateY(0)';
        }, 100);
    }

    function addBlankLine() {
        const blankLineElement = document.createElement('div');
        blankLineElement.className = 'message';
        chatBox.appendChild(blankLineElement);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    sendButton.addEventListener('click', () => {
        const userMessage = userInput.value.trim();
        if (userMessage !== '') {
            addMessageToChatBox(userMessage, 'User');
            fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message: userMessage })
            })
            .then(response => response.json())
            .then(data => {
                if (data.response) {
                    addMessageToChatBox(data.response, 'LLaMA', true);
                }
            })
            .catch(error => {
                console.error('Error:', error);
            });
            userInput.value = '';
        }
    });

    userInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            sendButton.click();
        }
    });

    logoutButton.addEventListener('click', () => {
        logoutButton.disabled = true; // Disable button during logout process
        fetch('/logout', {
            method: 'POST'
        })
        .then(() => {
            window.location.href = '/';
        })
        .catch(error => {
            console.error('Error:', error);
            logoutButton.disabled = false; // Re-enable button on error
        });
    });

    copyButton.addEventListener('click', () => {
        copyButton.disabled = true; // Disable button during copy process
        const messages = chatBox.querySelectorAll('.message');
        let chatContent = '';
        messages.forEach((message) => {
            chatContent += `${message.textContent}\n\n`;
        });
        navigator.clipboard.writeText(chatContent)
            .then(() => {
                alert('Chat copied to clipboard!');
                copyButton.disabled = false; // Re-enable button after successful copy
            })
            .catch(error => {
                console.error('Error:', error);
                copyButton.disabled = false; // Re-enable button on error
            });
    });

    clearButton.addEventListener('click', () => {
        clearButton.disabled = true; // Disable button during clear process
        fetch('/clear', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                chatBox.innerHTML = '';
                addMessageToChatBox('Hi! How can I assist you today?', 'LLaMA');
                clearButton.disabled = false; // Re-enable button after successful clear
            }
        })
        .catch(error => {
            console.error('Error:', error);
            clearButton.disabled = false; // Re-enable button on error
        });
    });
}
