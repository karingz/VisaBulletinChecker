from flask import Flask, jsonify
import visa_bulletin_checker  # Rename your script as a module

app = Flask(__name__)

@app.route("/")
def check_bulletin():
    result = visa_bulletin_checker.run_check()  # Move logic into a function
    return f"<pre>{result}</pre>"

if __name__ == "__main__":
    app.run()
