from flask import Flask, render_template, request, redirect, flash
from flask_jwt_extended import create_access_token
from jinja2 import Environment, FileSystemLoader
app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = "jungleclass301team3"
app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
app.config["JWT_COOKIE_SAMESITE"] = "Lax"
app.config["JWT_COOKIE_HTTPONLY"] = True
jwt = JWTManager(app)

import requests
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from bson.objectid import ObjectId


client = MongoClient('mongodb://jungle:qwer1234@43.202.33.208', 27017)
db = client.firstProject
db.users.create_index([("userId", 1)], unique=True)

@app.route("/login")
def home():
    return render_template('login.html')

@app.route("/signup")
def signup_page():
    return render_template('signup.html')

@app.route("/checkidduplicate",methods=["GET"])
def checkIdDuplicate():
    id=request.args.get('user_id')
    
    check_id = db.users.find_one({'userId' : id})

    if check_id:
        return jsonify({"success": False, "message": "이미 존재하는 ID입니다."}), 200
    else:
        return jsonify({"success": True, "message": "사용 가능한 ID입니다."}), 200
    
@app.route("/signup",methods=["POST"])
def singup():
    name = request.form["user_name"]
    userId = request.form["user_id"]
    password = request.form["user_password"]
    birthday = request.form["birthday"]
    kakaoId = request.form["kakao_id"]
    hashed_password = generate_password_hash(password)
    
    users = {
        'name' : name,
        'userId' : userId,
        'password' : hashed_password,
        'birthday' : birthday,
        'kakaoId' : kakaoId,
        'posts_ids' : []
    }
    
    result = db.users.insert_one(users)
    
    if result.acknowledged:
        return jsonify({'result': True})
    else:
        return jsonify({'result': False})
    
@app.route("/login",methods=["POST"])
def login():
    user_id = request.form['user_id']
    password = request.form['password']
    
    find_user = db.users.find_one({
        'userId':user_id,
        'password':password
    })
    
    if find_user:
        access_token = create_access_token(identity = user_id)
        response = make_response(jsonify({'result': True}))
        set_access_cookies(response, access_token)
        return response
    else:
        return jsonify({'result':False})

@app.route("/posting",methods=["POST"])
@jwt_required()
def posting():
    title = request.form['post_title']
    postType = request.form['post_type']
    meetDate = request.form['meet_date']
    dueDate = request.form['due_date']
    capacity = request.form['capacity']
    content = request.form['content']
    
    nowTime = datetime.datetime.now()
    author_id = get_jwt_identity()
    
    post = {
        'title' : title,
        'author' : author_id,
        'postType' : postType,
        'meetDate' : meetDate,
        'dueDate' : dueDate,
        'nowPersonnel' : 1,
        'goalPersonnel' : capacity,
        'content' : content,
        'createdAt' : nowTime,
        'updatedAt' : nowTime,
        'attendPeople' : [author_id]
    }
    
    result = db.posts.insert_one(post)
    
    if result.acknowledged:
        return jsonify({'result': True})
    else:
        return jsonify({'result': False})

@app.route("/postlist",methods = ["GET"])
@jwt_required()
def findAllPost():
    current_user = get_jwt_identity()
    pipeline = [
        {
            "$addFields": {
                "isJoined": {"$in": [current_user, "$attendPeople"]}
            }
        },
        {
            "$sort": {"createdAt": 1}
        }
    ]
    posts = list(db.posts.aggregate(pipeline))
    for post in posts:
        post['_id']=str(post['_id'])
        
        
    return jsonify({'result': True, 'posts': posts})

@app.route("/filter", methods=["GET"])
@jwt_required()
def applyFilter():
    condition = request.args.get('condition')
    current_user = get_jwt_identity()
    pipeline = [
        {
        "$addFields": {
                "isJoined": {"$in": [current_user, "$attendPeople"]}
            }
        },
        {
            "$sort" : {"createdAt":1}
        }
    ] 
    posts = list(db.posts.aggregate(pipeline))
    
    for post in posts:
        post['_id'] = str(post['_id'])
    
    return jsonify({'result': True, 'posts': posts})

@app.route("/applymeeting",methods=["PUT"])
@jwt_required()
def applymeeting():
    _id = ObjectId(request.form['_id'])
    current_user = get_jwt_identity()
    
    find_post = db.posts.find_one({'_id':_id})
    attend_list = find_post.get('attendPeople', [])
    
    result = db.posts.find_one_and_update(
        {
            '_id': _id,
            '$expr': { '$lt': [ { '$size': "$attendPeople" }, "$goalPersonnel" ] },
            'attendPeople': { '$ne': current_user }
        },
        {
            '$addToSet': { 'attendPeople': current_user },
            '$inc': { 'nowPersonnel': 1 }
        },
        return_document=ReturnDocument.AFTER
    )

    if result:
        return jsonify({'result': True, 'message': '신청 완료되었습니다.'}), 200
    else:
        return jsonify({'result': False, 'message': '신청 실패: 정원이 초과되었거나 이미 신청하였습니다.'}), 400

if __name__ == "__main__":
    app.run('0.0.0.0',port=5001,debug=True)