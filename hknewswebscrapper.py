import logging
import traceback
import datetime
import time
import pandas as pd
import pickle
import traceback
from pytz import timezone, utc
from flask import Flask, request, render_template, redirect, url_for, jsonify, send_file
from flask.logging import default_handler
from flask.json import JSONEncoder
from copy import deepcopy

import webscrapper

def custom_time(*args):
    utc_dt = utc.localize(datetime.datetime.utcnow())
    my_tz = timezone("Asia/Kolkata")
    converted = utc_dt.astimezone(my_tz)
    return converted.timetuple()


formatter = logging.Formatter('[%(asctime)s.%(msecs)03d] (%(process)d:%(thread)d) %(levelname)s '
                              '%(filename)s{%(funcName)s:%(lineno)d}:  %(message)s', datefmt="%a %b %d %H:%M:%S")
formatter.converter = custom_time
default_handler.setFormatter(formatter)


app = Flask(__name__)
app.logger.setLevel(logging.INFO)
app.logger.info("Starting!!!")


def _validate(req, expected_fields):
    if not all(field in req and req[field] for field in expected_fields):
        return False, "Not all fields are passed"
    if pd.to_datetime(req['end_date']) >= datetime.datetime.today():
        return False, "End date should be T - 1 or lesser"
    return True, ""


@app.route("/")
def start():
    return render_template('homepage.html')


@app.route("/trend_plot/", methods=['GET', 'POST'])
def trend_plot():
    app.logger.info("Received Order {}, args {}  {}".format(request, request.form, request.json))

    validated, error = _validate(request.form, ("start_date", "end_date", "stock_code"))
    if not validated:
        app.logger.error("Incorrect request payload {}".format(error))
        return error, 500

    res = webscrapper.get_shareholding_trend(request.form['start_date'], request.form['end_date'], request.form['stock_code'])
    app.logger.info("Sending response")
    return jsonify(res)


@app.route("/transaction_finder/", methods=['GET', 'POST'])
def transaction_finder():
    app.logger.info("Received Order {}, args {}  {}".format(request, request.form, request.json))

    validated, error = _validate(request.form, ("start_date", "end_date", "stock_code", "threshold"))
    if not validated:
        app.logger.error("Incorrect request payload {}".format(error))
        return error, 500

    res = webscrapper.get_transactions(request.form['start_date'], request.form['end_date'],
                                       request.form['stock_code'], float(request.form['threshold']))
    return jsonify(res)


if __name__ == "__main__":
    app.run(debug=True)
