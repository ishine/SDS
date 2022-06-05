import sqlite3




db  = sqlite3.connect("./recipes.db")
db.execute("create table if not exists data (name TEXT, rating TEXT, ease TEXT, notes TEXT, type TEXT, prep_time TEXT, photo TEXT, cookbook TEXT, page TEXT, ingredients TEXT, slowcooker TEXT,  link TEXT, last_made TEXT, make_it_next TEXT)")
SEP = "##"

with open("./recipes.csv") as f:
    lines = f.readlines()
    for l in lines[1:]:
        spl = l.split(SEP)
        db.execute("insert into data (name, rating, ease, notes, type, prep_time, photo, cookbook, page, ingredients, slowcooker, link, last_made, make_it_next) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", spl)
    db.commit()
    db.close()

    
