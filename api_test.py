import unittest
import requests

class TestChatAPI(unittest.TestCase):

    def setUp(self):
        self.base_url = "http://127.0.0.1:5000"
        self.session_cookie = None

    # def test_register(self):
    #     data = {
    #         "username": "testuser2",
    #         "password": "testuser2"
    #     }
    #     response = requests.post(f"{self.base_url}/register", data=data)
    #     self.assertEqual(response.status_code, 200)

    def test_login(self):
        data = {
            "username": "admin",
            "password": "password"
        }
        response = requests.post(f"{self.base_url}/login", json=data)
        self.assertEqual(response.status_code, 200)
        self.session_cookie = response.cookies.get('session')
        print('login successful!')

    def test_chat(self):
        if not self.session_cookie:
            self.test_login()
        data = {
            "message": "Hello"
        }
        response = requests.post(f"{self.base_url}/chat", json=data, cookies={'session': self.session_cookie})
        self.assertEqual(response.status_code, 200)
        print("Chat Response:", response.json())

if __name__ == "__main__":
    unittest.main()
