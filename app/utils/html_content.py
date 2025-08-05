html_content = """
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>API IPCA com Portal da Transparência</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 15px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                overflow: hidden;
            }
            
            .header {
                background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
                color: white;
                padding: 40px;
                text-align: center;
            }
            
            .header h1 {
                font-size: 2.5rem;
                margin-bottom: 10px;
                font-weight: 300;
            }
            
            .header p {
                font-size: 1.2rem;
                opacity: 0.9;
            }
            
            .content {
                padding: 40px;
            }
            
            .section {
                margin-bottom: 40px;
            }
            
            .section h2 {
                color: #2c3e50;
                margin-bottom: 20px;
                font-size: 1.8rem;
                border-bottom: 2px solid #3498db;
                padding-bottom: 10px;
            }
            
            .endpoints-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                gap: 25px;
                margin-top: 25px;
            }
            
            .endpoint-card {
                background: #f8f9fa;
                border-radius: 10px;
                padding: 25px;
                border-left: 5px solid #3498db;
                transition: transform 0.3s ease, box-shadow 0.3s ease;
            }
            
            .endpoint-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 10px 25px rgba(0,0,0,0.1);
            }
            
            .endpoint-method {
                display: inline-block;
                padding: 5px 12px;
                border-radius: 20px;
                font-size: 0.8rem;
                font-weight: bold;
                margin-bottom: 10px;
            }
            
            .get { background: #27ae60; color: white; }
            .post { background: #e74c3c; color: white; }
            
            .endpoint-path {
                font-family: 'Courier New', monospace;
                background: #2c3e50;
                color: white;
                padding: 10px;
                border-radius: 5px;
                margin: 10px 0;
                font-size: 0.9rem;
                word-break: break-all;
            }
            
            .endpoint-description {
                color: #666;
                margin-top: 10px;
            }
            
            .quick-links {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-top: 30px;
            }
            
            .quick-link {
                background: linear-gradient(135deg, #3498db, #2980b9);
                color: white;
                padding: 25px;
                border-radius: 10px;
                text-decoration: none;
                text-align: center;
                transition: all 0.3s ease;
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 10px;
            }
            
            .quick-link:hover {
                transform: translateY(-3px);
                box-shadow: 0 10px 20px rgba(52, 152, 219, 0.3);
                color: white;
                text-decoration: none;
            }
            
            .quick-link i {
                font-size: 2rem;
            }
            
            .feature-list {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-top: 20px;
            }
            
            .feature-item {
                padding: 20px;
                background: linear-gradient(135deg, #f39c12, #e67e22);
                color: white;
                border-radius: 10px;
                text-align: center;
            }
            
            .feature-item i {
                font-size: 2rem;
                margin-bottom: 15px;
                display: block;
            }
            
            .footer {
                background: #2c3e50;
                color: white;
                text-align: center;
                padding: 25px;
                margin-top: 40px;
            }
            
            @media (max-width: 768px) {
                .endpoints-grid {
                    grid-template-columns: 1fr;
                }
                
                .header h1 {
                    font-size: 2rem;
                }
                
                .content {
                    padding: 20px;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1><i class="fas fa-chart-line"></i> API IPCA com Portal da Transparência</h1>
                <p>Correção monetária com dados do IPCA e integração com Portal da Transparência do Paraná</p>
            </div>
            
            <div class="content">
                <div class="section">
                    <h2><i class="fas fa-rocket"></i> Links Rápidos</h2>
                    <div class="quick-links">
                        <a href="/docs" class="quick-link">
                            <i class="fas fa-book"></i>
                            <span>Documentação Swagger</span>
                        </a>
                        <a href="/redoc" class="quick-link">
                            <i class="fas fa-file-alt"></i>
                            <span>Documentação ReDoc</span>
                        </a>
                        <a href="/transparencia/status" class="quick-link">
                            <i class="fas fa-server"></i>
                            <span>Status da Integração</span>
                        </a>
                    </div>
                </div>
                
                <div class="section">
                    <h2><i class="fas fa-chart-bar"></i> Endpoints IPCA</h2>
                    <div class="endpoints-grid">
                        <div class="endpoint-card">
                            <span class="endpoint-method get">GET</span>
                            <div class="endpoint-path">/ipca</div>
                            <div class="endpoint-description">
                                <strong>Retorna todos os dados do IPCA</strong><br>
                                Obtém valores históricos do IPCA desde dezembro de 1993
                            </div>
                        </div>
                        
                        <div class="endpoint-card">
                            <span class="endpoint-method get">GET</span>
                            <div class="endpoint-path">/ipca/filtro?mes=12&ano=2023</div>
                            <div class="endpoint-description">
                                <strong>Consulta IPCA por mês/ano</strong><br>
                                Filtra dados do IPCA para um período específico
                            </div>
                        </div>
                        
                        <div class="endpoint-card">
                            <span class="endpoint-method get">GET</span>
                            <div class="endpoint-path">/ipca/corrigir?valor=1000&mes_inicial=01&ano_inicial=2020&mes_final=12&ano_final=2023</div>
                            <div class="endpoint-description">
                                <strong>Correção monetária pelo IPCA</strong><br>
                                Corrige valores monetários entre datas usando variação do IPCA
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="section">
                    <h2><i class="fas fa-search"></i> Endpoints Portal da Transparência</h2>
                    <div class="endpoints-grid">
                        <div class="endpoint-card">
                            <span class="endpoint-method post">POST</span>
                            <div class="endpoint-path">/transparencia/consultar</div>
                            <div class="endpoint-description">
                                <strong>Consulta dados com correção automática</strong><br>
                                Busca dados do Portal da Transparência do PR e aplica correção monetária pelo IPCA
                                <br><br>
                                <em>Payload: {"data_inicio":"01/2020", "data_fim":"12/2023"}</em>
                            </div>
                        </div>
                        
                        <div class="endpoint-card">
                            <span class="endpoint-method get">GET</span>
                            <div class="endpoint-path">/transparencia/status</div>
                            <div class="endpoint-description">
                                <strong>Status da integração</strong><br>
                                Verifica se a API_crawler está disponível e funcionando
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="section">
                    <h2><i class="fas fa-star"></i> Características Principais</h2>
                    <div class="feature-list">
                        <div class="feature-item">
                            <i class="fas fa-database"></i>
                            <h3>Dados do IPEA</h3>
                            <p>Acesso direto aos dados oficiais do IPCA via IPEA</p>
                        </div>
                        
                        <div class="feature-item">
                            <i class="fas fa-calculator"></i>
                            <h3>Correção Automática</h3>
                            <p>Correção monetária automática dos valores encontrados</p>
                        </div>
                        
                        <div class="feature-item">
                            <i class="fas fa-sync"></i>
                            <h3>Consultas Assíncronas</h3>
                            <p>Suporte a consultas de múltiplos anos com dados parciais</p>
                        </div>
                        
                        <div class="feature-item">
                            <i class="fas fa-shield-alt"></i>
                            <h3>API Robusta</h3>
                            <p>Tratamento de erros e validação de dados integrados</p>
                        </div>
                    </div>
                </div>
                
                <div class="section">
                    <h2><i class="fas fa-info-circle"></i> Como Usar</h2>
                    <div style="background: #f8f9fa; padding: 25px; border-radius: 10px; border-left: 5px solid #17a2b8;">
                        <h4>Exemplo de consulta ao Portal da Transparência:</h4>
                        <div style="background: #2c3e50; color: white; padding: 15px; border-radius: 5px; margin: 15px 0; font-family: monospace;">
curl -X POST "http://localhost:8000/transparencia/consultar" \\<br>
&nbsp;&nbsp;&nbsp;&nbsp; -H "Content-Type: application/json" \\<br>
&nbsp;&nbsp;&nbsp;&nbsp; -d '{"data_inicio":"01/2020", "data_fim":"03/2022"}'
                        </div>
                        <p><strong>Resultado:</strong> Dados do Portal da Transparência com correção monetária aplicada. Cada ano é corrigido separadamente para o ano atual.</p>
                    </div>
                </div>
            </div>
            
            <div class="footer">
                <p><i class="fas fa-code"></i> API IPCA v1.0.0 | <i class="fas fa-university"></i> Dados oficiais do IPEA | <i class="fas fa-heart"></i> Desenvolvido para TCC</p>
            </div>
        </div>
    </body>
    </html>
    """