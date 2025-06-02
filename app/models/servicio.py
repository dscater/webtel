from app import db

class Servicio(db.Model):
    __tablename__ = 'servicios'
    id = db.Column(db.Integer, primary_key=True)
    cineplus = db.Column(db.Integer, nullable=False)
    cloudgames = db.Column(db.Integer, nullable=False)
    soundplus = db.Column(db.Integer, nullable=False)
    librosgo = db.Column(db.Integer, nullable=False)
    def __repr__(self):
        return f"<Servicio {self.id}>"