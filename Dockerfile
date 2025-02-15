# Usa uma imagem oficial do Python 3.10.12
FROM python:3.10.12  

# Define a pasta principal dentro do contêiner
WORKDIR /app  

# Copia os arquivos do projeto para dentro do contêiner
COPY . /app  

# Instala as dependências do projeto
RUN pip install --upgrade pip  
RUN pip install -r requirements.txt  

# Define o comando que inicia o projeto
CMD ["python", "app.py"]  # Troque "app.py" pelo seu arquivo principal
