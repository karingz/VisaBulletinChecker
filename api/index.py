from flask import Flask
import VisaBulletinChecker  # Import the module

app = Flask(__name__)

@app.route("/")
def check_bulletin():
    result = VisaBulletinChecker.run_check()  # Call the function
    return jsonify(result)

if __name__ == "__main__":
    app.run()
