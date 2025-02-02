from datetime import datetime, timezone, timedelta
from flask import request
from flask_restx import Namespace, Resource, fields

#JWT imports
from flask_jwt_extended import create_refresh_token, get_jwt, get_jwt_identity, create_access_token, jwt_required
#Email validation
from email_validator import EmailNotValidError, validate_email
#Databse Models
from models import Users
from models import TokenBlocklist
#custom in built modules created
from .password_validation import is_strong_password
from .helpers import add_token_to_database, revoke_token, is_token_revoked

#extensions
from extensions import db, jwt


rest_api= Namespace("auth",version="1.0", description="Authentication related operations")

#Required Feilds/Models while using the flask_restex APIs

signup_model = rest_api.model('SignUpModel', {
    "Fname": fields.String(required=True, min_length=2, max_length=32),
    "Lname": fields.String(required=True, min_length=2, max_length=32),
    "email": fields.String(required=True, min_length=4, max_length=254),
    "password": fields.String(required=True, min_length=4, max_length=128)
})

login_model = rest_api.model('LoginModel', {
    "email": fields.String(required=True, min_length=4, max_length=64),
    "password": fields.String(required=True, min_length=4, max_length=16)
})

user_edit_model = rest_api.model('UserEditModel', {
    "userID": fields.String(required=True, min_length=1, max_length=32),
    "username": fields.String(required=True, min_length=2, max_length=32),
    "email": fields.String(required=True, min_length=4, max_length=64)
})






#Signup Api Creates new user by using the signup template above.
@rest_api.route('/api/users/register')
class Register(Resource):

    @rest_api.expect(signup_model, validate=True)
    def post(self):

        print("touched!")
        request_data=request.get_json()
        _Fname =request_data.get("Fname")
        _Lname =request_data.get("Lname")
        _email = request_data.get("email")
        _passwd = request_data.get("password")

        email_exist = Users.get_by_email(_email)

        #check how valid the email is 
        try:
            valid=validate_email(_email)
            

        except EmailNotValidError as e:

            return {"success": False, "msg": "This email format is invalid"}


        # Check if email exists
        if  email_exist:
            
            return {"success": False, "msg": "This email already exists."}, 400
        
        # Check password strength
        if is_strong_password(_passwd)==False:
       
            return {"success": False, "msg": "strong password must have at least one uppercase letter (A-Z), at least one lowercase letter (a-z), at least one digit (0-9), at least one special character from the set: !@#$%^&*, and a minimum length of 8 characters."}, 400
        
        _uname= _Fname+"."+_Lname
        new_user = Users(username=_uname, email= _email )
        new_user.set_password(_passwd)
        new_user.save()

        return {"success": True, "UserID": new_user.id,"msg": "The user was successfully registered"}, 200


#login for the registered user
@rest_api.route('/api/users/login')
class LoginUser(Resource):
    
    @rest_api.expect(login_model, validate= True)
    def post(self):
        print("touched1")
        if not request.is_json:
            return {"msg": "Missing JSON in request"}, 400

        req_data = request.get_json()
       
        _email = req_data.get("email")
        _passwd = req_data.get("password")

        user_exist = Users.get_by_email(_email)

        if not user_exist:
            return {"success": False, "msg": "Incorrect Credentials"}, 400
        
        if not user_exist.check_password(_passwd):
            return {"success": False, "msg": "Incorrect Credentials"}, 400
        
        #create_access_token
        access_token = create_access_token(identity=user_exist.id)
        refresh_token = create_refresh_token(identity=user_exist.id)

        user=Users.get_by_id(user_exist.id)
        user.set_jwt_auth_active(True)
        user.save()

        #Add the tokens to the database
        add_token_to_database(access_token)
        add_token_to_database(refresh_token)

        return {"success": True, "Access_token": access_token, "Refresh_token": refresh_token, "user": user_exist.toJSON()}, 200




#Editing username or email or both 
#protected route 2
@rest_api.route('/api/users/edit')  
class EditUser(Resource):
        
    @rest_api.expect(user_edit_model, validate=True)
    @jwt_required()
    def post(self):

        req_data = request.get_json()
        #current_user_id = get_jwt_identity()
        #print(current_user_id)
        #self=Users.get_by_id(current_user_id)
        new_uname = req_data.get("username")
        new_email = req_data.get("email")
        #validation
        email_exist= Users.get_by_email(self)


         #check email format
        try:
            valid=validate_email(new_email)

        except EmailNotValidError as e:

            return {"success": False, "msg": "This email format is invalid."}


        # Check if email exists
        if  email_exist:
            return {"success": False, "msg": "This email already exists."}, 400
        

        if new_uname:
                self.update_username(new_uname)

        if new_email:
                self.update_email(new_email)

        self.save()

        return {"success": True, "msg": "User records updates successfully !"}, 200
    

    #Refresh the Token
    #protected route 3
    @rest_api.route('/api/users/refresh')
    class RefreshToken(Resource):
        @jwt_required(refresh=True)
        def post(self):
            user_id = get_jwt_identity()
            access_token = create_access_token(identity=user_id)
            add_token_to_database(access_token)
            return {"success": True,"access_token": access_token}, 200

    #Logout User 
    #protected route 4           
    @rest_api.route('/api/users/logout')
    class LogoutUser(Resource):
        @jwt_required()
        def post(self):
            jti=get_jwt()["jti"]
            user_id = get_jwt_identity()
            revoke_token(jti, user_id)

            user=Users.get_by_id(user_id)
            print(user_id,user)
            user.set_jwt_auth_active(False)
            user.save()
            return {"success": True, "msg": "User logged-out successfully !"}, 200
    
    
    #Revoke User token 
    #protected route 5        
    @rest_api.route("/revoke_access")
    class RevokeAccessTokenResource(Resource):
        @jwt_required()
        def delete(self):
            jti = get_jwt()["jti"]
            user_id = get_jwt_identity()
            revoke_token(jti, user_id)
            return {"success": True,"msg": "Token revoked"}, 200
        

    #Revoke User Refresh token
    #protected route 6    
    @rest_api.route("/revoke_refresh")
    class RevokeRefreshTokenResource(Resource):
        @jwt_required(refresh=True)
        def delete(self):
            jti = get_jwt()["jti"]
            user_id = get_jwt_identity()
            revoke_token(jti, user_id)
            return {"success": True,"msg": "Refresh token revoked"}, 200
        

    #Check if toklen has been sent to blocklist
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_headers, jwt_payload):
        try:
            return is_token_revoked(jwt_payload)
        except Exception:
            return True

    #@JWT_Manager.user_lookup_loader
    #def load_user(jwt_headers, jwt_payload):
     #   user_id = jwt_payload[.get("JWT_IDENTITY_CLAIM")]
      #  return User.query.get(user_id)

