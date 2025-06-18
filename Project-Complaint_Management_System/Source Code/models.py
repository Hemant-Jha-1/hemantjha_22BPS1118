from pymongo import MongoClient
from datetime import datetime
from config import Config

class Database:
    def __init__(self):
        self.client = MongoClient(Config.MONGO_URI)
        self.db = self.client[Config.DATABASE_NAME]
        self.users = self.db.users
        self.complaints = self.db.complaints
        self._create_indexes()
    
    def _create_indexes(self):
        """Create database indexes for performance"""
        self.users.create_index("username", unique=True)
        self.complaints.create_index("user")
        self.complaints.create_index("status")
        self.complaints.create_index("created_at")

class User:
    def __init__(self, db):
        self.collection = db.users
    
    def create(self, username, password_hash, role='user'):
        user_data = {
            'username': username,
            'password_hash': password_hash,
            'role': role,
            'created_at': datetime.utcnow()
        }
        return self.collection.insert_one(user_data)
    
    def find_by_username(self, username):
        return self.collection.find_one({'username': username})
    
    def exists(self, username):
        return self.collection.count_documents({'username': username}) > 0

class Complaint:
    def __init__(self, db):
        self.collection = db.complaints
    
    def create(self, title, description, user, priority='medium'):
        complaint_data = {
            'title': title,
            'description': description,
            'user': user,
            'status': 'pending',
            'priority': priority,
            'feedback': None,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        return self.collection.insert_one(complaint_data)
    
    def find_by_user(self, username):
        return list(self.collection.find({'user': username}).sort('created_at', -1))
    
    def find_all(self):
        return list(self.collection.find().sort('created_at', -1))
    
    def find_by_id(self, complaint_id):
        from bson import ObjectId
        try:
            return self.collection.find_one({'_id': ObjectId(complaint_id)})
        except:
            return None
    
    def update_status(self, complaint_id, status, admin_user):
        from bson import ObjectId
        try:
            return self.collection.update_one(
                {'_id': ObjectId(complaint_id)},
                {
                    '$set': {
                        'status': status,
                        'updated_at': datetime.utcnow(),
                        'updated_by': admin_user
                    }
                }
            )
        except:
            return None
    
    def add_feedback(self, complaint_id, feedback):
        from bson import ObjectId
        try:
            return self.collection.update_one(
                {'_id': ObjectId(complaint_id)},
                {
                    '$set': {
                        'feedback': feedback,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
        except:
            return None
    
    def delete(self, complaint_id):
        from bson import ObjectId
        try:
            return self.collection.delete_one({'_id': ObjectId(complaint_id)})
        except:
            return None