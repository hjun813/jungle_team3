from flask import Flask, render_template, request, redirect, flash, url_for, session, jsonify,make_response
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, set_access_cookies, get_jwt_identity
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient, ReturnDocument
from bson.objectid import ObjectId
import os
import requests

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['JWT_SECRET_KEY'] = "jungleclass301team3"
app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
app.config["JWT_COOKIE_CSRF_PROTECT"] = False
app.config["JWT_COOKIE_SAMESITE"] = "Lax"
app.config["JWT_COOKIE_HTTPONLY"] = True
jwt = JWTManager(app)


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
    post_id = request.args.get("id")  # URL에서 게시물 ID 가져오기
    title = request.args.get("title", "")
    post_type = request.args.get("postType", "")
    meet_date = request.args.get("meetDate", "")
    due_date = request.args.get("dueDate", "")
    details = request.args.get("details", "")
    goal_personnel = request.args.get("goalPersonnel", "")
    
    return render_template('posting.html',post_id=post_id, title=title, post_type=post_type,
                           meet_date=meet_date, due_date=due_date,
                           details=details, goal_personnel=goal_personnel)

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
        access_token = create_access_token(identity=user_id, expires_delta=False)
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
        return redirect(url_for("findPost"))
    else:
        return render_template("posting.html")

@app.route("/postlist",methods = ["GET"])
@jwt_required()
def findPost():
    current_user = get_jwt_identity()
    now = datetime.now()
    
    filter_type = request.args.get("post_type")  # 게시물 유형 필터링
    sort = request.args.get("sort_type","latest")
    page = int(request.args.get("page", 1))  # 페이지 (기본값: 1)
    per_page = 30  # 페이지당 문서 개수
    skip_count = (page - 1) * per_page 
    
    query = {"dueDate": {"$gte": now}}
    
    if filter_type and filter_type != "ALL":
        query['postType'] = filter_type
    
    if sort == "latest":
        sort_field = "createdAt"
        sort_value = -1
    elif sort == "shortest":
        sort_field = "dueDate"
        sort_value =1
    
    pipeline = [
        {"$match": query},  # 마감일이 지나지 않은 게시물만 조회
        {"$addFields": {"isJoined": {"$in": [current_user, "$attendPeople"]}}},  # 현재 사용자가 참석했는지 여부 추가
        {"$sort": {sort_field: sort_value}},  # 선택한 정렬 기준 적용
        {"$skip": skip_count},  # 해당 페이지의 첫 번째 문서까지 건너뛰기
        {"$limit": per_page}  # 페이지당 문서 개수 제한
    ]
    posts = list(db.posts.aggregate(pipeline))

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

@app.route("/applymeeting",methods=["POST"])
@jwt_required()
def applymeeting():
    _id = ObjectId(request.form['_id'])
    current_user = get_jwt_identity()
    # find_post = db.posts.find_one({'_id':_id})
    
    result = db.posts.find_one_and_update(
        {
            '_id': _id,
            '$expr': { '$lte': [ { '$size': "$attendPeople" }, "$goalPersonnel" ] },
            'attendPeople': { '$nin': [current_user] }
        },
        {
            '$addToSet': { 'attendPeople': current_user },
            '$inc': { 'nowPersonnel': 1 }
        },
        return_document=ReturnDocument.AFTER
    )

    if result:
        # 여기서 만약 모집 정원이 다 되었으면 이벤트 로그 생성 메서드로 넘어가기
        return redirect(url_for("findPost"))
    else:
        return redirect(url_for("findPost"))
    
@app.route("/cancelmeeting",methods=["POST"])
@jwt_required()
def cancelmeeting():
    current_user = get_jwt_identity()
    _id = ObjectId(request.form['_id'])
    
    postAuthor = db.posts.find_one({'_id':_id},{'_id': 0, 'author':1})
    
    if current_user == postAuthor['author']:
        flash("작성자는 참가 취소가 불가능 합니다.","error")
        return redirect(url_for("findPost"))
    
    result = db.posts.find_one_and_update(
        {
            '_id': _id,
            'attendPeople': { '$in': [current_user] }
        },
        {
            '$pull': { 'attendPeople': current_user },  
            '$inc': { 'nowPersonnel': -1 }
        },
        return_document=ReturnDocument.AFTER
    )
    
    if result:
        return redirect(url_for("findPost"))
    else:
        return redirect(url_for("findPost"))
    
@app.route("/mypage/mypost",methods=["GET"])
@jwt_required()
def mypost():
    current_user = get_jwt_identity()
    
    myposts = list(db.posts.find({"author": current_user}))  # 리스트로 변환
    
    for post in myposts:
        post['_id'] = str(post['_id'])
        if isinstance(post['meetDate'], datetime):
            post['meetDate'] = post['meetDate'].strftime("%Y-%m-%d")
        if isinstance(post['dueDate'], datetime):
            post['dueDate'] = post['dueDate'].strftime("%Y-%m-%d")
        
    if myposts:
        return render_template("mypage_mypost.html", posts = myposts)
    else:
        flash("조회 실패 새로고침하세요")
        return render_template("mypage_mypost.html")
        

@app.route("/mypage/applypost",methods=["GET"])    
@jwt_required()
def applypost():
    current_user = get_jwt_identity()
    
    allposts = list(db.posts.find({}))
    
    attendposts = list()
    
    for post in allposts:
        post['_id'] = str(post['_id'])
        if current_user in post['attendPeople']:
            if isinstance(post['meetDate'], datetime):
                post['meetDate'] = post['meetDate'].strftime("%Y-%m-%d")
            if isinstance(post['dueDate'], datetime):
                post['dueDate'] = post['dueDate'].strftime("%Y-%m-%d")
                attendposts.append(post)
            
    
    if len(attendposts) >= 0:
        return render_template("mypage_myapply.html", posts = attendposts)
    else:
        flash("조회 실패거나 조회할 게시물이 없습니다. 새로고침 하세요")
        return render_template("mypage_myapply.html")

@app.route("/updatepost",methods=["POST"])
@jwt_required()
def updatepost():
    current_user=get_jwt_identity()
    _id = ObjectId(request.form['_id'])
    
    title = request.form.get('post_title')
    postType = request.form.get('post_type')
    meetDate = request.form.get('meet_date')
    dueDate = request.form.get('due_date')
    capacity = request.form.get('capacity')
    details = request.form.get('details')
    updatedAt = datetime.now()
    
    find_post = db.posts.find_one_and_update(
        {'_id':_id},
        {
            "$set" : {
                'title': title,
                'postType': postType,
                'meetDate': meetDate,
                'dueDate': dueDate,
                'goalPersonnel': capacity,
                'details': details,
                'updatedAt': updatedAt
            }
        },
        return_document=ReturnDocument.AFTER
    )
    
    if find_post:
        flash("게시글이 성공적으로 수정되었습니다.", "success")
        return redirect(url_for("mypost"))  # 게시글 리스트 페이지로 이동
    else:
        flash("게시글 수정에 실패했습니다.", "error")
        return redirect(url_for("mypost"))
    
    
if __name__ == "__main__":
    app.run('0.0.0.0',port=5001,debug=True)