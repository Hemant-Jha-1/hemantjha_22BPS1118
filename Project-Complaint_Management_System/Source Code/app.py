from flask import Flask, request, jsonify, session
from models import Database, User, Complaint
from auth import hash_password, verify_password, login_required, admin_required
from config import Config
from datetime import datetime
import json

class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle MongoDB ObjectId and datetime"""
    def default(self, obj):
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        from bson import ObjectId
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

app = Flask(__name__)
app.config.from_object(Config)
app.json_encoder = CustomJSONEncoder

# Initialize Database
db = Database()
user_model = User(db.db)
complaint_model = Complaint(db.db)

# ================================
# AUTHENTICATION ROUTES
# ================================

@app.route('/api/register', methods=['POST'])
def register():
    """User Registration"""
    try:
        data = request.get_json()
        
        # Validation
        if not data or not data.get('username') or not data.get('password'):
            return jsonify({'error': 'Username and password are required'}), 400
        
        username = data['username'].strip()
        password = data['password']
        role = data.get('role', 'user').lower()
        
        # Validate role
        if role not in ['user', 'admin']:
            return jsonify({'error': 'Invalid role. Must be user or admin'}), 400
        
        # Check if user exists
        if user_model.exists(username):
            return jsonify({'error': 'Username already exists'}), 400
        
        # Hash password and create user
        password_hash = hash_password(password)
        result = user_model.create(username, password_hash, role)
        
        return jsonify({
            'message': 'User registered successfully',
            'user_id': str(result.inserted_id),
            'username': username,
            'role': role
        }), 201
        
    except Exception as e:
        return jsonify({'error': 'Registration failed', 'details': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    """User Login"""
    try:
        data = request.get_json()
        
        # Validation
        if not data or not data.get('username') or not data.get('password'):
            return jsonify({'error': 'Username and password are required'}), 400
        
        username = data['username'].strip()
        password = data['password']
        
        # Find user
        user = user_model.find_by_username(username)
        if not user or not verify_password(password, user['password_hash']):
            return jsonify({'error': 'Invalid username or password'}), 400
        
        # Create session
        session['user'] = {
            'id': str(user['_id']),
            'username': user['username'],
            'role': user['role']
        }
        
        return jsonify({
            'message': 'Login successful',
            'user': {
                'username': user['username'],
                'role': user['role']
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Login failed', 'details': str(e)}), 500

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    """User Logout"""
    session.pop('user', None)
    return jsonify({'message': 'Logged out successfully'}), 200

# ================================
# COMPLAINT ROUTES
# ================================

@app.route('/api/complaints', methods=['POST'])
@login_required
def create_complaint():
    """Create a new complaint"""
    try:
        data = request.get_json()
        
        # Validation
        if not data or not data.get('title') or not data.get('description'):
            return jsonify({'error': 'Title and description are required'}), 400
        
        title = data['title'].strip()
        description = data['description'].strip()
        priority = data.get('priority', 'medium').lower()
        
        # Validate priority
        if priority not in ['low', 'medium', 'high', 'urgent']:
            return jsonify({'error': 'Invalid priority. Must be low, medium, high, or urgent'}), 400
        
        # Create complaint
        result = complaint_model.create(title, description, session['user']['username'], priority)
        
        return jsonify({
            'message': 'Complaint created successfully',
            'complaint_id': str(result.inserted_id),
            'title': title,
            'priority': priority,
            'status': 'pending'
        }), 201
        
    except Exception as e:
        return jsonify({'error': 'Failed to create complaint', 'details': str(e)}), 500

@app.route('/api/complaints', methods=['GET'])
@login_required
def get_complaints():
    """Get complaints (user sees their own, admin sees all)"""
    try:
        current_user = session['user']
        
        if current_user['role'] == 'admin':
            # Admin sees all complaints
            complaints = complaint_model.find_all()
            message = f"Retrieved {len(complaints)} total complaints"
        else:
            # User sees only their complaints
            complaints = complaint_model.find_by_user(current_user['username'])
            message = f"Retrieved {len(complaints)} complaints for {current_user['username']}"
        
        # Convert ObjectId to string for JSON serialization
        for complaint in complaints:
            complaint['_id'] = str(complaint['_id'])
            complaint['created_at'] = complaint['created_at'].isoformat()
            complaint['updated_at'] = complaint['updated_at'].isoformat()
        
        return jsonify({
            'message': message,
            'complaints': complaints,
            'total': len(complaints)
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve complaints', 'details': str(e)}), 500

@app.route('/api/complaints/<complaint_id>', methods=['GET'])
@login_required
def get_complaint(complaint_id):
    """Get a specific complaint"""
    try:
        complaint = complaint_model.find_by_id(complaint_id)
        
        if not complaint:
            return jsonify({'error': 'Complaint not found'}), 404
        
        current_user = session['user']
        
        # Check permissions (user can only see their own, admin sees all)
        if current_user['role'] != 'admin' and complaint['user'] != current_user['username']:
            return jsonify({'error': 'Access denied'}), 403
        
        # Convert ObjectId to string
        complaint['_id'] = str(complaint['_id'])
        complaint['created_at'] = complaint['created_at'].isoformat()
        complaint['updated_at'] = complaint['updated_at'].isoformat()
        
        return jsonify({
            'message': 'Complaint retrieved successfully',
            'complaint': complaint
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve complaint', 'details': str(e)}), 500

@app.route('/api/complaints/<complaint_id>/status', methods=['PUT'])
@admin_required
def update_complaint_status(complaint_id):
    """Update complaint status (Admin only)"""
    try:
        complaint_id = request.view_args['complaint_id']
        data = request.get_json()
        
        if not data or not data.get('status'):
            return jsonify({'error': 'Status is required'}), 400
        
        status = data['status'].lower()
        valid_statuses = ['pending', 'in-progress', 'resolved', 'closed', 'rejected']
        
        if status not in valid_statuses:
            return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
        
        # Check if complaint exists
        complaint = complaint_model.find_by_id(complaint_id)
        if not complaint:
            return jsonify({'error': 'Complaint not found'}), 404
        
        # Update status
        result = complaint_model.update_status(complaint_id, status, session['user']['username'])
        
        if result and result.modified_count > 0:
            return jsonify({
                'message': 'Complaint status updated successfully',
                'complaint_id': complaint_id,
                'new_status': status,
                'updated_by': session['user']['username']
            }), 200
        else:
            return jsonify({'error': 'Failed to update complaint status'}), 500
        
    except Exception as e:
        return jsonify({'error': 'Failed to update complaint status', 'details': str(e)}), 500

@app.route('/api/complaints/<complaint_id>/feedback', methods=['PUT'])
@login_required
def add_feedback(complaint_id):
    """Add feedback to a resolved complaint"""
    try:
        data = request.get_json()
        
        if not data or not data.get('feedback'):
            return jsonify({'error': 'Feedback is required'}), 400
        
        feedback = data['feedback'].strip()
        
        # Check if complaint exists
        complaint = complaint_model.find_by_id(complaint_id)
        if not complaint:
            return jsonify({'error': 'Complaint not found'}), 404
        
        current_user = session['user']
        
        # Check permissions (only complaint owner can add feedback)
        if complaint['user'] != current_user['username']:
            return jsonify({'error': 'You can only add feedback to your own complaints'}), 403
        
        # Check if complaint is resolved
        if complaint['status'] not in ['resolved', 'closed']:
            return jsonify({'error': 'Feedback can only be added to resolved or closed complaints'}), 400
        
        # Add feedback
        result = complaint_model.add_feedback(complaint_id, feedback)
        
        if result and result.modified_count > 0:
            return jsonify({
                'message': 'Feedback added successfully',
                'complaint_id': complaint_id,
                'feedback': feedback
            }), 200
        else:
            return jsonify({'error': 'Failed to add feedback'}), 500
        
    except Exception as e:
        return jsonify({'error': 'Failed to add feedback', 'details': str(e)}), 500

@app.route('/api/complaints/<complaint_id>', methods=['DELETE'])
@admin_required
def delete_complaint(complaint_id):
    """Delete a complaint (Admin only)"""
    try:
        # Check if complaint exists
        complaint = complaint_model.find_by_id(complaint_id)
        if not complaint:
            return jsonify({'error': 'Complaint not found'}), 404
        
        # Delete complaint
        result = complaint_model.delete(complaint_id)
        
        if result and result.deleted_count > 0:
            return jsonify({
                'message': 'Complaint deleted successfully',
                'complaint_id': complaint_id,
                'deleted_by': session['user']['username']
            }), 200
        else:
            return jsonify({'error': 'Failed to delete complaint'}), 500
        
    except Exception as e:
        return jsonify({'error': 'Failed to delete complaint', 'details': str(e)}), 500

# ================================
# UTILITY ROUTES
# ================================

@app.route('/api/status', methods=['GET'])
def system_status():
    """System health check"""
    try:
        # Test database connection
        db.client.admin.command('ping')
        
        # Get statistics
        user_count = db.users.count_documents({})
        complaint_count = db.complaints.count_documents({})
        pending_complaints = db.complaints.count_documents({'status': 'pending'})
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'statistics': {
                'total_users': user_count,
                'total_complaints': complaint_count,
                'pending_complaints': pending_complaints
            },
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@app.route('/api/profile', methods=['GET'])
@login_required
def get_profile():
    """Get current user profile"""
    current_user = session['user']
    user_complaints = complaint_model.find_by_user(current_user['username'])
    
    # Count complaints by status
    status_counts = {}
    for complaint in user_complaints:
        status = complaint['status']
        status_counts[status] = status_counts.get(status, 0) + 1
    
    return jsonify({
        'user': {
            'username': current_user['username'],
            'role': current_user['role']
        },
        'statistics': {
            'total_complaints': len(user_complaints),
            'status_breakdown': status_counts
        }
    }), 200

# ================================
# ERROR HANDLERS
# ================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'error': 'Method not allowed'}), 405

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ================================
# MAIN APPLICATION
# ================================

if __name__ == '__main__':
    print("🚀 Starting Smart Complaint Management System (SCMS)")
    print("📡 API Server running on: http://localhost:5000")
    print("📊 Database:", Config.DATABASE_NAME)
    print("🔐 Session-based authentication enabled")
    print("\n📋 Available API Endpoints:")
    print("   POST /api/register        - User registration")
    print("   POST /api/login           - User login")
    print("   POST /api/logout          - User logout")
    print("   POST /api/complaints      - Create complaint")
    print("   GET  /api/complaints      - Get complaints")
    print("   GET  /api/complaints/<id> - Get specific complaint")
    print("   PUT  /api/complaints/<id>/status - Update status (Admin)")
    print("   PUT  /api/complaints/<id>/feedback - Add feedback")
    print("   DELETE /api/complaints/<id> - Delete complaint (Admin)")
    print("   GET  /api/profile         - Get user profile")
    print("   GET  /api/status          - System health check")
    print("\n🧪 Use Postman to test the API endpoints!")
    
    app.run(debug=Config.DEBUG, host='0.0.0.0', port=5000)