from flask import Flask, render_template, request, redirect, flash, url_for, session, jsonify,make_response
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, set_access_cookies, get_jwt_identity
from jinja2 import Environment, FileSystemLoader
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['JWT_SECRET_KEY'] = "jungleclass301team3"
app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
app.config["JWT_COOKIE_CSRF_PROTECT"] = False
app.config["JWT_COOKIE_SAMESITE"] = "Lax"
app.config["JWT_COOKIE_HTTPONLY"] = True
jwt = JWTManager(app)

import requests
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from bson.objectid import ObjectId


client = MongoClient("mongodb://localhost:27017/")
db = client.firstProject
# db.users.create_index([("userId", 1)], unique=True)

@app.route("/")
def home():
    return render_template('login.html')

@app.route("/signup")
def signup_page():
    return render_template('signup.html')

@app.route("/posting",methods=["GET"])
def posting_page():
    return render_template('posting.html')

@app.route("/checkduplicate", methods=["GET"])
def checkIdDuplicate():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"result": False, "message": "아이디를 입력하세요."}), 400

    check_id = db.users.find_one({"userId": user_id})
    if check_id:
        return jsonify({"result": False, "message": "이미 존재하는 ID입니다."}), 200
    else:
        return jsonify({"result": True, "message": "사용 가능한 ID입니다."}), 200
    
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("user_name")
        userId = request.form.get("user_id")
        password = request.form.get("user_password")
        kakaoId = request.form.get("kakao_id")

        if not name or not userId or not password:
            flash("모든 필드를 입력하세요.", "error")
            return redirect(url_for("signup"))

        hashed_password = generate_password_hash(password)

        user = {
            "name": name,
            "userId": userId,
            "password": hashed_password,
            "kakaoId": kakaoId,
            "posts_ids": []
        }

        result = db.users.insert_one(user)

        if result.acknowledged:
            flash("회원가입이 완료되었습니다. 로그인하세요.", "success")
            return redirect(url_for("home"))  # 로그인 페이지로 리디렉션
        else:
            flash("회원가입 실패", "error")
            return redirect(url_for("signup"))

    return render_template("signup.html")

@app.route("/login",methods=["POST"])
def login():
    user_id = request.form.get("user_id")
    password = request.form.get("password")
    
    hashed_password = generate_password_hash(password)
    
    find_user = db.users.find_one({'userId':user_id})
    
    if find_user and check_password_hash(find_user['password'], password):
        access_token = create_access_token(identity=user_id)
        response =redirect(url_for("findPost"))
        set_access_cookies(response, access_token)
        return response
    else:
        return render_template("login.html", error="아이디 또는 비밀번호가 잘못되었습니다.")

@app.route("/posting",methods=["POST"])
@jwt_required()
def posting():
    title = request.form['post_title']
    postType = request.form['post_type']
    meetDate = request.form['meet_date']
    dueDate = request.form['due_date']
    capacity = request.form['capacity']
    details = request.form['details']
    
    nowTime = datetime.now()
    author_id = get_jwt_identity()
    
    post = {
        'title' : title,
        'author' : author_id,
        'postType' : postType,
        'meetDate' : datetime.strptime(meetDate,"%Y-%m-%d"),
        'dueDate' : datetime.strptime(dueDate,"%Y-%m-%d"),
        'nowPersonnel' : 1,
        'goalPersonnel' : capacity,
        'details' : details,
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
def findPost():
    current_user = get_jwt_identity()
    now = datetime.now()
    
    filter_type = request.args.get("post_type")  # 게시물 유형 필터링
    sort = request.args.get("sort_type","createdAt")
    page = int(request.args.get("page", 1))  # 페이지 (기본값: 1)
    per_page = 30  # 페이지당 문서 개수
    skip_count = (page - 1) * per_page 
    
    query = {"dueDate": {"$gte": now}}
    
    if filter_type:
        query['postType'] = filter_type
    
    if sort == "createdAt":
        sort_field = "createdAt"
        sort_value = -1
    elif sort == "soonest":
        sort_field = "dueDate"
        sort_value =1
        
    post=db.posts.find({})
    
    # dueDate 필드의 데이터 타입 확인
    if post and "dueDate" in post:
        print(f"dueDate 값: {post['dueDate']}, 타입: {type(post['dueDate'])}")
    else:
        print("dueDate 필드가 없습니다.")
    
    pipeline = [
        {"$match": query},  # 마감일이 지나지 않은 게시물만 조회
        {"$addFields": {"isJoined": {"$in": [current_user, "$attendPeople"]}}},  # 현재 사용자가 참석했는지 여부 추가
        {"$sort": {sort_field: sort_value}},  # 선택한 정렬 기준 적용
        {"$skip": skip_count},  # 해당 페이지의 첫 번째 문서까지 건너뛰기
        {"$limit": per_page}  # 페이지당 문서 개수 제한
    ]
    posts = list(db.posts.aggregate(pipeline))
    
    print(len(posts))
    
    for post in posts:
        post['_id']=str(post['_id'])
        post['meetDate']=post['meetDate'].strftime("%Y-%m-%d")
        post['dueDate']=post['dueDate'].strftime("%Y-%m-%d")
        
    total_posts = db.posts.count_documents(query)
    total_pages = (total_posts + per_page - 1) // per_page
    
    return render_template("postlist.html", 
                           posts=posts,
                           current_page=page,
                           total_pages=total_pages,
                           total_posts=total_posts,
                           filter_due=sort,)



@app.route("/applymeeting",methods=["PUT"])
@jwt_required()
def applymeeting():
    _id = ObjectId(request.form['_id'])
    current_user = get_jwt_identity()
    
    # find_post = db.posts.find_one({'_id':_id})
    
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
        # 여기서 만약 모집 정원이 다 되었으면 이벤트 로그 생성 메서드로 넘어가기
        return render_template("post_list.html", result = True, message = '신청 완료되었습니다.'), 200
    else:
        return render_template("post_list.html", result = False, message = '신청 실패: 정원이 초과되었거나 이미 신청하였습니다.'), 400
    
@app.route("/cancelmeeting",methods=["PUT"])
@jwt_required()
def cancelmeeting():
    current_user = get_jwt_identity()
    _id = ObjectId(request.json['_id'])
    
    result = db.posts.find_one_and_update(
        {
            '_id': _id,
            '$expr': { '$lt': [ { '$size': "$attendPeople" }, "$goalPersonnel" ] },
            'attendPeople': { '$in': current_user }
        },
        {
        '$pull': { 'attendPeople': current_user },  
        '$inc': { 'nowPersonnel': -1 }
        },
        return_document=ReturnDocument.AFTER
    )
    
    
    if result:
        return render_template("post_list.html", result = True, message = '신청 취소가 완료되었습니다.'), 200
    else:
        return render_template("post_list.html", result = False, message = '신청 취소가 실패했습니다.'), 400
    

    
if __name__ == "__main__":
    app.run('0.0.0.0',port=5001,debug=True)