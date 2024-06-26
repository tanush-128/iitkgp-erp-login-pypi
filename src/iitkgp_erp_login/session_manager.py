import jwt
from typing import Dict
from datetime import datetime, timedelta
from threading import Timer
import erp
import requests

# Constants
SECRET_KEY = 'your_secret_key'  # Use a secure secret key for JWT
HEADERS = {
                'timeout': '20',
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/51.0.2704.79 Chrome/51.0.2704.79 Safari/537.36'
            }
class Session:
    def __init__(self):
        self.requests_session =  requests.Session()  
        self.session_token = None
        self.sso_token = None
        self.last_acccessed = datetime.now()

class SessionManager:
    _instance = None
    sessions: Dict[str, Session]
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SessionManager, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, headers: Dict[str, str] = None, secret_key: str = None):
        if not hasattr(self, 'initialized'):  # To ensure __init__ is called only once
            self.sessions = {}
            self.headers = headers or HEADERS
            self.secret_key = secret_key or SECRET_KEY
            self.initialized = True
            self.cleanup_sessions()

    def generate_jwt(self, roll):
        payload = {
            'roll': roll,
            'exp': datetime.now() + timedelta(minutes=30)  # Token expiration time
        }
        token = jwt.encode(payload, self.secret_key, algorithm='HS256')
        return token

    def verify_jwt(self, token):
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            return payload['roll']
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")

    def create_session(self, roll):
        token = self.generate_jwt(roll)
        session = Session()
        self.sessions[token] = session
        return token

    def get_secret_question(self, token):
        roll = self.verify_jwt(token)
        session = self.sessions.get(token)
        if not session:
            raise ValueError(f"No session found for token")
        
        session_token = erp.get_sessiontoken(session.requests_session)
        session.session_token = session_token
        secret_question = erp.get_secret_question(self.headers, session.requests_session, roll)
        return secret_question

    def request_otp(self, token, passw, secret_answer):
        roll = self.verify_jwt(token)
        session = self.sessions.get(token)
        if not session:
            raise ValueError(f"No session found for token")

        login_details = erp.get_login_details(roll, passw, secret_answer, session.session_token)
       
        erp.request_otp(self.headers, session.requests_session, login_details)

    def establish_erp_session(self, token,password, answer, email_otp):
        roll = self.verify_jwt(token)
        session = self.sessions.get(token)
        if not session or not session.login_details:
            raise ValueError(f"No login details found for token")
        login_details = erp.LoginDetails(
            user_id=roll,
            password=password,
            answer=answer,
            typeee='SI',
            sessionToken=session.session_token,
            requestedUrl=erp.HOMEPAGE_URL,
            email_otp=email_otp
        )
        sso_token = erp.signin(self.headers, session.requests_session, login_details)
        session.sso_token = sso_token
        return session

    def get_erp_session(self, token):
        roll = self.verify_jwt(token)
        session = self.sessions.get(token)
        if not session: 
            raise ValueError(f"No ERP session found for token")
        
        return session

    def end_session(self, token):
        if token in self.sessions:
            del self.sessions[token]
        return "Session ended"

    def cleanup_sessions(self):
        now = datetime.now()
        expired_sessions = [token for token, session in self.sessions.items()
                            if now - session.last_acccessed > timedelta(minutes=10)]
        for token in expired_sessions:
            del self.sessions[token]
        # Schedule the next cleanup in 10 minutes
        Timer(600, self.cleanup_sessions).start()