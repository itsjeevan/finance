import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Select the total shares owned by user, grouped by symbol
    stocks = db.execute("SELECT symbol, SUM(shares) as total_shares FROM purchases WHERE user_id=:id GROUP BY symbol HAVING total_shares > 0", id=session["user_id"])

    # Select user's cash
    cash = db.execute("SELECT cash FROM users where user_id =:id", id=session["user_id"])
    cash = round(cash[0]["cash"], 2)
    total = cash

    quotes = {}
    prices = {}

    # Put current stock information into dictionaries
    for stock in stocks:

        quotes[stock["symbol"]] = lookup(stock["symbol"])
        total_shares_price = stock["total_shares"] * quotes[stock["symbol"]]["price"]
        prices[stock["symbol"]] = format(total_shares_price, '.2f')
        total += total_shares_price

    # Format values to two decimal places
    cash = format(cash, '.2f')
    total = format(total, '.2f')

    return render_template("index.html", prices=prices, stocks=stocks, quotes=quotes, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Collect symbol information (symbol, name, price) based off user's input
        symbol_info = lookup(request.form.get("symbol"))

        # Ensure a valid symbol was passed
        if not symbol_info:
            return apology("must provide valid symbol", 400)

        # Reject floating-point values of shares
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("must provide valid shares", 400)

        # Calculate cost to purchase shares
        price = symbol_info["price"]
        cost = shares * price

        # Select user's cash
        cash = db.execute("SELECT cash FROM users WHERE user_id=:id", id=session["user_id"])
        cash = cash[0]["cash"]

        # Reject zero or negative share value
        if shares <= 0:
            return apology("must provide valid shares", 400)

        # Ensure user has enough cash to purchase shares
        elif cost > cash:
            return apology("not enough funds", 400)

        # Insert purchase into database
        symbol = symbol_info["symbol"]
        db.execute("INSERT INTO purchases (user_id, symbol, shares, price) VALUES(:user_id, :symbol, :shares, :price)", user_id=session["user_id"], symbol=symbol, shares=shares, price=price)

        # Update user's cash
        db.execute("UPDATE users SET cash = cash - :cost WHERE user_id=:id", cost=cost, id=session["user_id"])

        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Select all purchases made by user
    purchases = db.execute("SELECT symbol, shares, price, timestamp FROM purchases WHERE user_id=:id", id=session["user_id"])

    return render_template("history.html", purchases=purchases)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username=:username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["user_id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Collect symbol information (symbol, name, price) based off user's input
        symbol_info = lookup(request.form.get("symbol"))

        # Ensure a valid symbol was passed
        if not symbol_info:
            return apology("must provide valid symbol", 400)

        return render_template("symbol.html", name=symbol_info["name"], symbol=symbol_info["symbol"], price=symbol_info["price"])

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Store user's input into variables
        username = request.form.get("username")
        password = request.form.get("password")
        confirm_password = request.form.get("confirmation")

        # Ensure username was submitted
        if not username:
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not password or not confirm_password:
            return apology("must provide password", 400)

        # Ensure passwords match
        elif password != confirm_password:
            return apology("passwords do not match", 400)

        # Hash user's password and place in database along with username
        hash = generate_password_hash(password)
        new_user = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", username=username, hash=hash)

        # Ensure username is not taken
        if not new_user:
            return apology("username is taken", 400)

        # Login the new user automatically
        session["user_id"] = new_user

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        symbol = request.form.get("symbol")

        # Ensure a symbol was selected from drop-down list
        if not symbol:
            return apology("must provide valid symbol", 400)

        # Reject floating-point values of shares
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("must provide valid shares", 400)

        # Select the user's total shares owned of a symbol
        stock = db.execute("SELECT SUM(shares) as total_shares FROM purchases WHERE user_id=:id AND symbol=:symbol", id=session["user_id"], symbol=request.form.get("symbol"))

        # Reject zero or negative share value
        if shares <= 0:
            return apology("too low shares", 400)

        # Ensure user has enough shares to sell
        elif shares > stock[0]["total_shares"]:
            return apology("don't own enough shares", 400)

        # Get price of all shares being sold
        symbol_info = lookup(symbol)
        price = symbol_info["price"]
        total_shares_price = shares * price

        # Insert transaction into database and update user's cash
        db.execute("INSERT INTO purchases (user_id, symbol, shares, price) VALUES(:user_id, :symbol, :shares, :price)", user_id=session["user_id"], symbol=symbol, shares=-shares, price=price)
        db.execute("UPDATE users SET cash = cash + :total_shares_price WHERE user_id=:id", total_shares_price=total_shares_price, id=session["user_id"])

        flash("Sold!")

        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        stocks = db.execute("SELECT symbol, SUM(shares) as total_shares FROM purchases WHERE user_id=:id GROUP BY symbol HAVING total_shares > 0", id=session["user_id"])

        return render_template("sell.html", stocks=stocks)


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


if __name__ == "__main__":
    app.debug = True
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port)
