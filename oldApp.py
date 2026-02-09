import pymysql
pymysql.install_as_MySQLdb()

from flask import Flask, redirect, render_template, url_for, flash, session
import joblib
from flask import request, jsonify
# from sklearn.neighbors import KNeighborsClassifier
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.preprocessing import LabelEncoder
from flask_mysqldb import MySQL
import pickle
# from sklearn.metrics.pairwise import euclidean_distances

import os
# Try to import SpeechRecognition and Pydub
try:
    import speech_recognition as sr
    from pydub import AudioSegment
    SPEECH_LIBS_AVAILABLE = True
except ImportError:
    SPEECH_LIBS_AVAILABLE = False
    print("Warning: SpeechRecognition or pydub not installed. Audio features will be disabled.")

app = Flask(__name__, template_folder='templates')

# MysQL Database
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'mendo-user'
app.config['MYSQL_PASSWORD'] = '120904'
app.config['MYSQL_DB'] = 'mendo'

shopsql = MySQL(app)
# MySQL Database

vectorizer = pickle.load(open('pred_vectorizer','rb'))
encoder = pickle.load(open('pred_encoder','rb'))

# knn = joblib.load("machine_learning_model/model_knn")
# svm = joblib.load("machine_learning_model/model_svm.pkl")

svm_model = pickle.load(open('machine_learning_model/svm_pred_model','rb'))

@app.route("/")

@app.route("/index")
def index():
	return render_template("index.html")

@app.route("/warning")
def warning():
    return render_template("warning.html")

@app.route("/disclaimer")
def disclaimer():
    return render_template("disclaimer.html")

@app.route("/welcome")
def welcome():
    return render_template("welcome.html")

@app.route("/assess", methods = ["GET", "POST"])
def assess():
    if request.method == "POST":
        input_data =  request.form["input_data"]
        
        # Vectorize user input
        print(f"📝 Step 1: Received Input")
        print(f"   \"{input_data}\"")
        
        user_input_vectorized = vectorizer.transform([input_data])
        
        # Explain tokens
        print(f"\n🔍 Step 2: Analyzing Key Terms (Tokenization)")
        feature_names = vectorizer.get_feature_names_out()
        # Get non-zero elements
        sorted_items = sorted(zip(user_input_vectorized.tocoo().col, user_input_vectorized.tocoo().data), key=lambda x: (x[1], x[0]), reverse=True)
        found_tokens = [feature_names[idx] for idx, _ in sorted_items]
        if found_tokens:
            print(f"   I found these meaningful words: {found_tokens}")
        else:
            print(f"   ⚠️ I didn't recognize any specific medical terms in this input.")

        # Predict with probabilities
        print(f"\n📊 Step 3: Calculating Probabilities")
        probabilities = svm_model.predict_proba(user_input_vectorized)[0]
        classes = encoder.classes_
        
        # Sort by probability
        prob_list = sorted(zip(classes, probabilities), key=lambda x: x[1], reverse=True)
        
        for medicine, prob in prob_list:
            bar_len = int(prob * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"   {medicine:<15} : {bar} {prob*100:.1f}%")
            
        # Predict the medicine (getting the top one)
        predicted_label = svm_model.predict(user_input_vectorized)
        
        # Decode the label to get the medicine
        predicted_medicine = encoder.inverse_transform(predicted_label)[0]
        
        print(f"\n🎯 Step 4: Final Decision")
        print(f"   I recommend: {predicted_medicine}")
        print(f"{'='*50}\n")
        
        
        cur = shopsql.connection.cursor()
        cur.execute("INSERT INTO predictiontable (input_text, prediction) VALUES (%s, %s)", (input_data, predicted_medicine,))
        shopsql.connection.commit()
        cur.close()
        return redirect(url_for("finished"))
        
    return render_template("assess.html")

@app.route("/transcribe", methods=["POST"])
def transcribe():
    if not SPEECH_LIBS_AVAILABLE:
        # If libs are missing, return 500 but also a helpful message
        return jsonify({"error": "Speech libraries (SpeechRecognition, pydub) not installed on server"}), 500

    if "audio_data" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio_data"]
    
    # Save temp file
    temp_path = "temp_audio.webm" # Browser MediaRecorder usually sends WebM/Ogg
    wav_path = "temp_audio.wav"
    audio_file.save(temp_path)

    try:
        # Convert to WAV (SpeechRecognition needs WAV/AIFF/FLAC)
        # We need ffmpeg installed on the system for this to work
        # If ffmpeg is missing, pydub will raise generic exception
        sound = AudioSegment.from_file(temp_path)
        sound.export(wav_path, format="wav")

        # Transcribe
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            # Try Google Web Speech API (default key)
            print("Sending audio to Google Speech API...")
            text = recognizer.recognize_google(audio_data)
            print(f"Transcription result: {text}")
            return jsonify({"text": text})

    except Exception as e:
        print(f"Transcription error: {str(e)}")
        error_msg = str(e)
        if "ffmpeg" in error_msg.lower():
             error_msg = "Server missing ffmpeg. Please install ffmpeg."
        return jsonify({"error": error_msg}), 500
    finally:
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)
        if os.path.exists(wav_path):
            os.remove(wav_path)

@app.route("/finished")
def finished():
    return render_template("finished.html")

@app.route("/result", methods = ["GET", "POST"])
def result():
    cur = shopsql.connection.cursor()
    cur.execute("SELECT * FROM predictiontable ORDER BY id DESC")
    item = cur.fetchall()
    cur.execute("DELETE FROM predictiontable")
    cur.close()
    return render_template("result.html", item=item)

@app.route("/assessagain")
def assessagain():
    cur = shopsql.connection.cursor()
    cur.execute("DELETE FROM predictiontable")
    shopsql.connection.commit()
    cur.close()
    return render_template("welcome.html")


@app.route("/shop")
def shop():
    curs = shopsql.connection.cursor()
    curs.execute('SELECT * FROM shopdatabase')
    item = curs.fetchall()
    curs.close()
    return render_template("shop.html", item=item)


@app.route("/itemdescription/<int:item_id>")
def itemdescription(item_id):
    cur = shopsql.connection.cursor()
    # SELECT * FROM shopdatabase WHERE item = :item_id LIMIT 1 ORDER BY item DESC LIMIT 1 ORDER    
    cur.execute("SELECT * FROM shopdatabase WHERE item_id = %s LIMIT 1", (item_id,))
    item = cur.fetchone()
    return render_template("itemdescription.html", item=item)

@app.route("/addtocart", methods = ["GET", "POST"])
def addtocart():
    cur = shopsql.connection.cursor()
    
    if request.method == "POST":
        try:
            item_id = request.form['item_id']
            qty = request.form['qty']
            item_name = request.form['item_name']
            
            # Check if quantity is greater than 0
            # if qty <= 0:
            #   flash("Invalid quantity. Quantity must be greater than 0.")
            #    return redirect(url_for("shop"))
            
            
            cur.execute("SELECT * FROM shopdatabase WHERE item_id = %s", (item_id,))
            item = cur.fetchall()
            
            if item:
                # Calculate total price
                # total_price = qty * item['price']
                
                cur.execute("INSERT INTO cartdatabase (item_id, item_name, qty) VALUES (%s,%s,%s)", (item_id, item_name, qty,))
                shopsql.connection.commit()
                flash("Item added to cart!")
            
            else:
                return "ITEM ALREADY ADDED TO CART!"
                
            return redirect(url_for("shop"))
        
        except Exception as e:
            return f"ERROR OCCURRED: Unable to add item to cart. {str(e)}"
    else:
        cur.execute("SELECT * FROM shopdatabase")
        item = cur.fetchall()
        print(type(item))
        return render_template("shop.html", item=item)
        

@app.route("/cart", methods=["GET", "POST"])
def cart():
    cur = shopsql.connection.cursor()
    cur.execute("""
        SELECT shopdatabase.item_id, shopdatabase.item_name, cartdatabase.qty, shopdatabase.price
        FROM shopdatabase
        INNER JOIN cartdatabase ON shopdatabase.item_id = cartdatabase.item_id
    """)
    item = cur.fetchall()
    return render_template("cart.html", item=item)
    

@app.route('/deleteitem/<int:item_id>', methods=['GET','POST'])
def deleteitem(item_id):
    cur = shopsql.connection.cursor()
    cur.execute("DELETE FROM shopdatabase WHERE item_id = %s", (item_id,))
    shopsql.connection.commit()
    flash("Data has been deleted successfully!")
    cur.close()
    return redirect(url_for("admindashboard"))

@app.route('/cartitemdelete/<int:item_id>', methods=['GET','POST'])
def deletecartitem(item_id):
    cur = shopsql.connection.cursor()
    cur.execute("DELETE FROM cartdatabase WHERE item_id = %s", (item_id,))
    shopsql.connection.commit()
    flash("Item has been removed")
    cur.close()
    return redirect(url_for("cart"))


@app.post("/purchased")
def purchased():
    # get all the items from the cartdatabase
    cur = shopsql.connection.cursor()
    cur.execute("SELECT * FROM cartdatabase");
    items = cur.fetchall()
    
    # create outtable
    cur.execute("INSERT INTO outtable (total_price) VALUES (0.00)");
    shopsql.connection.commit()
    outtable_id = cur.lastrowid
    
    total_price = 0
    
    for item in items:
        # get medicine from shopdatabase
        cur.execute("SELECT * FROM shopdatabase WHERE item_id = %s", (item[0],))
        shopitem = cur.fetchone()
        
        # insert new entry into outtable
        cur.execute("INSERT INTO outtable_shopdatabase (item_id, price, qty, outtable_id) VALUES (%s, %s, %s, %s)", (item[0], shopitem[3], item[2], outtable_id))   
        
        # update the quantity from a specific item in the shopdatabase
        cur.execute("UPDATE shopdatabase SET qty = %s WHERE item_id = %s", (shopitem[2] - item[2], item[0]))
        
        # add price to the total price
        total_price += (shopitem[3] * item[2])
        
    
    # update total price from the specific outtable
    cur.execute("UPDATE outtable SET total_price = %s WHERE id = %s", (total_price, outtable_id))
    
    # delete all entries from the cartdatabase
    cur.execute("DELETE FROM cartdatabase")
    
    # commit the transaction
    shopsql.connection.commit()
    return render_template("purchased.html")


def array_merge(first_array, second_array):
    if isinstance(first_array, list) and isinstance (second_array, list):
        return first_array + second_array
    elif isinstance (first_array, dict) and isinstance(second_array,dict):
        return dict(list(first_array.items())) + list(second_array.items())
    elif isinstance(first_array,set) and isinstance(second_array,set):
        return first_array.union(second_array)
    return False
    

if __name__ == '__main__':
    app.secret_key = 'super secret key' # paki-change nalang ni later
    app.config['SESSION_TYPE'] = 'filesystem'
    app.run(debug=True)