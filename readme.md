# API IPCA

Uma API RESTful para consulta de dados do IPCA (Índice de Preços ao Consumidor Amplo) e correção monetária de valores com base nesse índice.

## Descrição

Este projeto implementa uma API que permite consultar os valores históricos do IPCA e realizar correções monetárias de valores entre diferentes períodos. Os dados são obtidos diretamente da base do IPEA (Instituto de Pesquisa Econômica Aplicada) através da biblioteca ipeadatapy.

## Funcionalidades

- Consulta de todos os valores do IPCA desde dezembro de 1993
- Filtragem de valores do IPCA por mês e ano específicos
- Correção monetária de valores com base na variação do IPCA entre datas
- Disponibilização dos dados via API RESTful com documentação automática
- Suporte a túnel ngrok para exposição da API

## Tecnologias Utilizadas

- [FastAPI](https://fastapi.tiangolo.com/): Framework web de alta performance
- [Pydantic](https://docs.pydantic.dev/): Validação de dados
- [ipeadatapy](https://github.com/ipea/ipeadatapy): Acesso aos dados do IPEA
- [pandas](https://pandas.pydata.org/): Manipulação e análise de dados
- [pyngrok](https://pyngrok.readthedocs.io/): Integração com ngrok para exposição da API
- [Uvicorn](https://www.uvicorn.org/): Servidor ASGI de alta performance

## Estrutura do Projeto
```plaintext	
apiIPCA/
├── app/
│   ├── main.py                  # Ponto de entrada da aplicação
│   ├── api/
│   │   └── routes/              # Endpoints da API
│   │       └── ipca_model.py
│   ├── core/
│   │   └── config.py            # Configurações da aplicação
│   ├── models/
│   │   └── ipca_model.py        # Modelos de dados
│   ├── services/
│   │   └── ipca_service.py      # Lógica de negócio
│   └── utils/
│       └── data_loader.py       # Carregamento de dados do IPEA
├── .env                         # Variáveis de ambiente
├── requirements.txt             # Dependências do projeto
└── README.md                    # Esta documentação
```


## Pré-requisitos

- Python 3.9 ou superior
- Conexão com internet para acesso aos dados do IPEA
- Conta no ngrok (opcional, para exposição da API)

## Instalação

1. Clone o repositório:
   ```bash
   git clone <url-do-repositório>
   cd apiIPCA
   ```
2. Crie e ative um ambiente virtual:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # Linux/Mac
   ```
3. Instale as dependências:
   ```bash
    pip install -r requirements.txt
    ```
4. Configure as variáveis de ambiente no arquivo `.env`:
    ```env
    NGROK_AUTH_TOKEN=<seu_token_ngrok>
    ENVIROMENT=development  # ou production
    ```
5. Execute a aplicação:
    ```bash
    uvicorn app.main:app --reload #Usando o uvicorn diretamente
    ```
A API estará disponível em `http://localhost:8000`. Se o ngrok estiver configurado, um túnel público também será criado e o URL será exibido no console.

## Endpoints da API
### GET /ipca
Retorna todos os valores do IPCA desde dezembro de 1993.
### GET /ipca/filtro?mes={mes}&ano={ano}
Retorna os valores do IPCA para um mês e ano específicos.

| Parâmetro | Tipo   | Descrição                          |
|-----------|--------|------------------------------------|
| mes       | int    | Mês para filtrar os dados (1-12), com 2 digitos   |
| ano       | int    | Ano para filtrar os dados (1993-2023) |

Exemplo de requisição:
```
GET /ipca/filtro?mes=01&ano=2023
```
Resposta
```json
{
  "data": "01/2023",
  "valor": 6508.4
}
```
Códigos de status:

| Código | Descrição |
|--------|-----------|
| 200    | Requisição bem-sucedida |
| 404    | Dados não encontrados para o mês/ano especificado |
| 422    | Parâmetros inválidos (mês/ano fora do intervalo) |

### GET /ipca/corrigir?valor={valor}&mes_inicial={mes_inicial}&ano_inicial={ano_inicial}&mes_final={mes_final}&ano_final={ano_final}
Realiza a correção monetária de um valor entre duas datas, retornando o valor corrigido e a variação do IPCA.
| Parâmetro       | Tipo   | Descrição                          |
|-----------------|--------|------------------------------------|
| valor           | float  | Valor a ser corrigido              |
| mes_inicial     | int    | Mês inicial (01-12)                 |
| ano_inicial     | int    | Ano inicial (1993-2023)            |
| mes_final       | int    | Mês final (01-12)                   |
| ano_final       | int    | Ano final (1993-2023)              |

Exemplo de requisição:
```
GET /ipca/corrigir?valor=1000&mes_inicial=01&ano_inicial=2020&mes_final=01&ano_final=2023
```
Resposta
```json
{
  "valor_inicial": 1000,
  "indice_ipca_inicial": 5331.42,
  "indice_ipca_final": 6508.4,
  "valor_corrigido": 1220.76
}
```

Códigos de status:
| Código | Descrição |
|--------|-----------|
| 200    | Requisição bem-sucedida |
| 422    | Parâmetros inválidos (mês/ano fora do intervalo) |
| 400    | Erro de validação (por exemplo, valor negativo) |
| 404    | Dados não encontrados para o período especificado |

### Documentação da API
A API possui documentação automática gerada pelo FastAPI, acessível nos seguintes endpoints:
- `GET /docs`: Documentação interativa da API (Swagger UI).
- `GET /redoc`: Documentação alternativa da API (ReDoc).

