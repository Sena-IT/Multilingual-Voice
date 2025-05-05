from flask import Flask, Response
from plivo import plivoxml

app = Flask(__name__)

@app.route('/receive_call/', methods=['GET','POST'])
def speak_xml():
    # Generate a Speak XML document with the details of the text to play on the call
    response = (plivoxml.ResponseElement()
            .add(plivoxml.SpeakElement('Hello, you just received your first call')))
    return Response(response.to_string(), mimetype='application/xml')

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)