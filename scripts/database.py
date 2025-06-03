import psycopg2
import os
import sys
import locale

# Configuração de codificação
print("Codificação padrão do terminal:", locale.getpreferredencoding())
print("Codificação de stdout:", sys.stdout.encoding)
print("Codificação de stderr:", sys.stderr.encoding)

# Reconfigura a codificação padrão de saída para UTF-8
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
# Define UTF-8 como padrão
os.environ["PYTHONIOENCODING"] = "utf-8"

# Função para conectar ao banco
def connect():
    try:
        conn = psycopg2.connect(
            host=os.environ['DB_HOST'],
            database=os.environ['DB_NAME'],
            user=os.environ['DB_USER'],
            password=os.environ['DB_PASSWORD'],
            port=os.environ.get('DB_PORT', 5432),
            client_encoding="UTF8",
        )
        print("Conexão estabelecida com sucesso.")
        return conn
    except Exception as e:
        print("Erro ao conectar ao banco:", e)
        return None
