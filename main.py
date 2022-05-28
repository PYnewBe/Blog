from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LogInForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)

# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# CONFIGURE TABLES
Base = declarative_base()


class User(UserMixin, db.Model, Base):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True, )
    email = db.Column(db.String(250), nullable=False, unique=True)
    password = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=False)
    posts = relationship("BlogPost", back_populates="comment_author")
    comments = relationship("Comment", back_populates="comment_author")


class BlogPost(db.Model, Base):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    author_id = db.Column(db.Integer, ForeignKey('users.id'))
    comment_author = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="parent_post")
    author = db.Column(db.String(250), nullable=False)


class Comment(db.Model, Base):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True, )
    text = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, ForeignKey('blog_posts.id'))
    parent_post_id = db.Column(db.Integer, ForeignKey('users.id'))
    comment_author = relationship("User", back_populates="comments")
    parent_post = relationship("BlogPost", back_populates="comments")


db.create_all()


# commenter image:
gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False, force_lower=False,
                    use_ssl=False, base_url=None)

# HANDLE LOGIN AND ACCESS:
login_manager = LoginManager()
login_manager.init_app(app)


# CUSTOM DECORATORS
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            user = current_user.id
        except AttributeError:
            user = None
        if user != 1:
            return abort(403)
        return f(*args, **kwargs)

    return decorated_function


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    try:
        user = current_user.id
    except AttributeError:
        user = None
    return render_template("index.html", all_posts=posts, user_id=user)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if request.method == "POST":
        if form.validate_on_submit():
            email = form.email.data
            if User.query.filter_by(email=email).first():
                print(User.query.filter_by(email=email).first())
                flash("You have already registered with this email address. Please, Log in. ", "error")
                return redirect(url_for("login"))
            else:
                password = generate_password_hash(password=form.password.data, method="pbkdf2:sha256", salt_length=8)
                new_user = User(
                    email=form.email.data,
                    password=password,
                    name=form.name.data
                )
            db.session.add(new_user)
            db.session.commit()
            user = User.query.filter_by(email=email).first()
            login_user(user)
            return redirect(url_for("get_all_posts"))

        else:
            return render_template("register.html", form=form)
    else:
        return render_template("register.html", form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LogInForm()
    if request.method == "GET":
        return render_template("login.html", form=form)
    else:
        user_email = request.form.get("email")
        user_password = request.form.get("password")
        user = User.query.filter_by(email=user_email).first()
        if user is not None:
            if check_password_hash(pwhash=user.password, password=user_password):
                login_user(user)
                return redirect(url_for('get_all_posts'))
            else:
                flash("Incorrect email-address or password.", "error")
                return render_template("login.html", form=form)
        else:
            flash("Incorrect email-address or password.", "error")
            return render_template("login.html", form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["POST", "GET"])
def show_post(post_id):
    try:
        user = current_user.id
    except AttributeError:
        user = None

    requested_post = BlogPost.query.get(post_id)
    comments = Comment.query.filter_by(parent_post_id=post_id).all()

    authors = []
    for comment in comments:
        author = User.query.get(comment.author_id)
        if author not in authors:
            authors.append(author)

    form = CommentForm()
    if request.method == "GET":
        return render_template("post.html", post=requested_post, user_id=user,
                               form=form, comments=comments, authors=authors)
    elif user is not None:
        if form.validate_on_submit():
            new_comment = Comment(
                text=form.comment_text.data,
                author_id=current_user.id,
                parent_post_id=post_id,
            )
            db.session.add(new_comment)
            db.session.commit()

        return redirect(url_for("show_post", post_id=post_id))
    else:
        flash("Please log in, to submit comments.", "error")
        return redirect(url_for("login"))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["GET", "POST"])
@admin_required
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author_id=current_user.id,
            author=current_user.name,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_required
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = post.author
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_required
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000,debug=False)
