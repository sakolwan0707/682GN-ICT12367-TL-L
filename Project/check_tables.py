from django.db import connection
try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
        tables = cursor.fetchall()
        for t in tables:
            print(t[0])
except Exception as e:
    print(f"Error: {e}")
