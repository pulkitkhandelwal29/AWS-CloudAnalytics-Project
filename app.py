from flask import Flask, request, render_template,url_for
from flask_cors import cross_origin
import boto3
import os
from werkzeug.utils import secure_filename
import speech_recognition as sr
import time


app = Flask(__name__)

@app.route("/")
@cross_origin()
def home():
    return render_template("index.html")


#Language Translation
@app.route("/languagetranslate", methods = ["GET", "POST"])
@cross_origin()
def languagetranslate():
    if request.method == "POST":
        text = request.form['texttotranslate']  
        sourcelanguage = request.form['sourcelanguage']
        targetlanguage = request.form['targetlanguage']
        translate = boto3.client(service_name='translate',region_name='us-east-1') 

        result = translate.translate_text(Text=text, SourceLanguageCode=sourcelanguage,TargetLanguageCode=targetlanguage) 

        translated = open("static/language/translated.txt","w+")
        translated.write(str(result["TranslatedText"]))

        return render_template("index.html",conversion="Your Text has been converted to your required language...")
    else:
        return render_template("index.html")


#Image to Text
@app.route("/imagetexttranslate", methods = ["GET", "POST"])
@cross_origin()
def imagetexttranslate():
    if request.method == "POST":
        image = request.files['image'] 

        filename = secure_filename(image.filename)
        image.save(os.path.join('static/uploads',filename))
        my_image = os.path.join('static/uploads',filename) 


        local_file = my_image
        s3_file_name='image.jpeg'
        bucket_name='imagetranslatebucket'

        def upload_to_aws(local_file, bucket, s3_file):
            s3 = boto3.client('s3')
            s3.upload_file(local_file, bucket, s3_file)
            print("Upload Successful")
            return True


        uploaded = upload_to_aws(local_file, bucket_name, s3_file_name)

        filename=s3_file_name
        bucket=bucket_name
        client = boto3.client('rekognition','us-east-1')
        response = client.detect_text(Image={'S3Object':{'Bucket':bucket,'Name':filename}})

        all_text = ''
        textDetections = response['TextDetections']
        for text in textDetections:
            all_text = all_text + text['DetectedText'] + ''

        text = all_text[:-(len(all_text) //2 )]

        translated = open("static/language/translated.txt","w+")
        translated.write(text)
        translated.close()  

        return render_template("index.html",conversion="Text has been extracted. To Translate refer Sentence Translator")
    else:
        return render_template("index.html")


#Audio to text
@app.route("/audiospeechtranslate", methods = ["GET", "POST"])
@cross_origin()
def audiospeechtranslate():
    if request.method == "POST":
        audio = request.files['audio'] 

        filename = secure_filename(audio.filename)
        audio.save(os.path.join('static/uploads',filename))
        my_audio = os.path.join('static/uploads',filename) 

        AUDIO_FILE = my_audio

        # use the audio file as the audio source                                        
        r = sr.Recognizer()
        with sr.AudioFile(AUDIO_FILE) as source:
            audio = r.record(source)  # read the entire audio file                  
            text = r.recognize_google(audio) 

        translated = open("static/language/translated.txt","w+")
        translated.write(str(text))       

        return render_template("index.html",conversion="Audio has been converted to text. To Translate refer Sentence Translator")
    else:
        return render_template("index.html")



#Document to text
@app.route("/documenttranslate", methods = ["GET", "POST"])
@cross_origin()
def documenttranslate():
    if request.method=='POST':

        def startJob(s3BucketName, objectName):
            response = None
            client = boto3.client('textract',region_name='us-east-1')
            response = client.start_document_text_detection(
            DocumentLocation={
                'S3Object': {
                    'Bucket': s3BucketName,
                    'Name': objectName
                }
            })

            return response["JobId"]

        def isJobComplete(jobId):
            # For production use cases, use SNS based notification 
            # Details at: https://docs.aws.amazon.com/textract/latest/dg/api-async.html
            time.sleep(5)
            client = boto3.client('textract',region_name='us-east-1')
            response = client.get_document_text_detection(JobId=jobId)
            status = response["JobStatus"]
            print("Job status: {}".format(status))

            while(status == "IN_PROGRESS"):
                time.sleep(5)
                response = client.get_document_text_detection(JobId=jobId)
                status = response["JobStatus"]
                print("Job status: {}".format(status))

            return status

        def getJobResults(jobId):

            pages = []

            client = boto3.client('textract',region_name='us-east-1')
            response = client.get_document_text_detection(JobId=jobId)
            
            pages.append(response)
            print("Resultset page recieved: {}".format(len(pages)))
            nextToken = None
            if('NextToken' in response):
                nextToken = response['NextToken']

            while(nextToken):

                response = client.get_document_text_detection(JobId=jobId, NextToken=nextToken)

                pages.append(response)
                print("Resultset page recieved: {}".format(len(pages)))
                nextToken = None
                if('NextToken' in response):
                    nextToken = response['NextToken']

            return pages

        pdf = request.files['pdf']

        filename = secure_filename(pdf.filename)
        pdf.save(os.path.join('static/uploads',filename))
        pdf_document = os.path.join('static/uploads',filename) 

        local_file = pdf_document
        s3_file_name='documenttotranslate.pdf'
        bucket_name='documenttranslate'

        def upload_to_aws(local_file, bucket, s3_file):
            s3 = boto3.client('s3')
            s3.upload_file(local_file, bucket, s3_file)
            print("Upload Successful")
            return True


        uploaded = upload_to_aws(local_file, bucket_name, s3_file_name)

        # Document
        s3BucketName = "documenttranslate"
        documentName = filename

        jobId = startJob(s3BucketName, documentName)
        print("Started job with id: {}".format(jobId))
        if(isJobComplete(jobId)):
            response = getJobResults(jobId)

        #print(response)

        # Print detected text
        for resultPage in response:
            for item in resultPage["Blocks"]:
                if item["BlockType"] == "LINE":
                    translated = open("static/language/translated.txt","w+")
                    translated.write(str(item["Text"]+''))
            translated.close()

        return render_template("index.html",conversion="Document has been converted to text. To Translate refer Sentence Translator")
    else:
        return render_template("index.html")



if __name__ == "__main__":
    app.run(debug=True)
