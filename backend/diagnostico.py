import sqlite3
conn = sqlite3.connect('/app/data/finance.db')
cur = conn.cursor()
cur.execute("""DELETE FROM transactions WHERE source='pluggy' OR payment_method='Pluggy' OR card_source IN('Nubank', 'Itaú')""")
print('apagadas:', cur.rowcount)
conn.commit()
conn.close()
