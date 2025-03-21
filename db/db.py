import sqlite3
import bcrypt
import yfinance as yf
from util import get_ticker_dict

class Database:
    def __init__(self, db_name="users.db", update_tickers=False):
        self.db_name = db_name
        if not self.is_init():
            self.create_schema()
            self._add_all_tickers()
        else:
            if update_tickers:
                self.update_all_tickers()
        
    ''' use private function connect to control how the db is modified
    '''
    def _connect(self):
        return sqlite3.connect(self.db_name)
    
    def create_schema(self):
        schema = '''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            balance REAL default 0.0,
            creation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS portfolios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            portfolio_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS tickers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker_symbol TEXT UNIQUE NOT NULL,
            current_price REAL,
            company_name TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS positions (
            portfolio_id INTEGER,
            ticker_id INTEGER,
            quantity INTEGER,
            purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            purchase_price REAL,
            PRIMARY KEY (portfolio_id, ticker_id, purchase_price),
            FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
            FOREIGN KEY (ticker_id) REFERENCES tickers(id) ON DELETE CASCADE
        );
        '''
        
        conn = self._connect()
        cursor = conn.cursor()
        cursor.executescript(schema)
        conn.commit()
        conn.close()
    
    def is_init(self):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('users', 'portfolios', 'tickers', 'positions')")
        tables = cursor.fetchall()
        
        if not tables:
            return False

        existing_tables = set(table[0] for table in tables)
        return {'users', 'portfolios', 'tickers', 'positions'}.issubset(existing_tables)
        
    def create_user(self, username, password, email=None):
        conn = self._connect()
        cursor = conn.cursor()
        
        encrypted_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        try:
            cursor.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)", (username, encrypted_pw, email))
            conn.commit()
        except sqlite3.IntegrityError:
            print("Error: user already exists")
            conn.close()
            return False
        
        conn.close()
        return True
            
                
    
    def verify_user(self, username, password):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user[1]):
            return True
        return False
        
    def delete_user(self, username):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE username=?", (username,))
        conn.commit()
        conn.close()
        
    def deposit(self, username, amount):
        old_balance = self.get_balance(username)
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = ? WHERE username = ?", (old_balance+amount, username,))
        conn.commit()
        conn.close()
        return True
    
    def withdrawal(self, username, amount):
        old_balance = self.get_balance(username)
        if old_balance - amount < 0:
            print("ERROR: cannot afford it")
            return False
        
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = ? WHERE username = ?", (old_balance-amount, username,))
        conn.commit()
        conn.close()
        
        
    def contains_user(self, username):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        user_exists = cursor.fetchone() is not None
        conn.close()
        return user_exists
    
    def get_balance(self, username:str):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE username = ?", (username,))
        balance = cursor.fetchone()[0]
        conn.close()
        return balance
    
    def create_ticker(self, symbol, name, price):
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO tickers (ticker_symbol, company_name, current_price) VALUES (?, ?, ?)", (symbol, name, price))
        except sqlite3.IntegrityError:
            conn.close()
            return False
        conn.commit()
        conn.close()
        return True
        
    def _add_all_tickers(self, debugLimit=50):
        
        ticker_dict = get_ticker_dict()
        for i, (tic, name) in enumerate(ticker_dict.items()):   
            price = yf.Ticker(tic).history(period="1d")["Close"].iloc[-1]
            self.create_ticker(tic, name, price)
            if debugLimit is not None and i > debugLimit:
                break

    
    def get_all_tickers(self):
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute("SELECT ticker_symbol, current_price FROM tickers")
        all_stocks = cursor.fetchall()
        conn.close()
        return all_stocks
        
        
    def update_ticker(self, symbol):
        stock = yf.Ticker(symbol)
        price_dat = stock.history('1d')
        current_price = price_dat["Close"].iloc[0]
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("UPDATE tickers SET current_price=? WHERE ticker_symbol=?", (current_price, symbol))
        conn.commit()
        conn.close()
        
    def update_all_tickers(self):
        ticker_dict = get_ticker_dict()
        for (tic, _) in ticker_dict.items():   
            self.update_ticker(tic)
        
    def delete_ticker(self, symbol):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tickers WHERE ticker_symbol=?", (symbol))
        conn.commit()
        conn.close()
        
        
    def create_portfolio(self, user_id, portfolio_name):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO portfolios (user_id, portfolio_name) VALUES (?, ?)", user_id, portfolio_name)
        conn.commit()
        conn.close()
        
    def delete_portfolio(self, user_id, portfolio_name):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM portfolios WHERE user_id=?, portfolio_name=?", user_id, portfolio_name)
        conn.commit()
        conn.close()
        
    def get_portfolio_positions(self, portfolio_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('''SELECT t.ticker_symbol, p.quantity FROM 
                            positions p JOIN tickers t ON 
                                pt.ticker_id = t.id WHERE 
                                    pt.portfolio_id = ?''', (portfolio_id, ))
        tickers = cursor.fetchall()
        conn.close()
        return tickers
    
    
    def buy_position(self, user_id, portfolio_id, ticker_id, quantity, amount):
        conn = self._connect()
        

if __name__ == "__main__":
    foo = Database()
    foo.get_all_tickers()