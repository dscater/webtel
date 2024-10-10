class Config:
    db_user = 'root'
    db_pass=''
    
    SQLALCHEMY_DATABASE_URI = 'mysql://'+db_user+':'+db_pass+'@localhost/webtel_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
