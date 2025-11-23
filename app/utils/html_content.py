html_content = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API IPCA & Transparência</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            /* Paleta baseada no Tailwind (Blue-500 / Purple-600) */
            --primary: #3b82f6;
            --primary-dark: #2563eb;
            --secondary: #9333ea;
            --bg-page: #f9fafb;
            --bg-card: #ffffff;
            --text-main: #1f2937; /* gray-800 */
            --text-muted: #6b7280; /* gray-500 */
            --border-color: #e5e7eb; /* gray-200 */
            
            --success: #10b981;
            --method-get: #0ea5e9; /* sky-500 */
            --method-post: #8b5cf6; /* violet-500 */
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background-color: var(--bg-page);
            color: var(--text-main);
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
        }

        /* Layout Principal */
        .wrapper {
            display: flex;
            flex-direction: column;
            min-height: 100vh;
        }

        /* Header inspirado na Navbar do Frontend */
        .navbar {
            background-color: var(--bg-card);
            border-bottom: 1px solid var(--border-color);
            padding: 1rem 0;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
        }

        .nav-content {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--text-main);
        }

        .brand i {
            color: var(--primary);
            font-size: 1.5rem;
        }

        /* Hero Section */
        .hero {
            background-color: var(--primary);
            color: white;
            padding: 3rem 0;
            text-align: center;
        }

        .hero h1 {
            font-size: 2.5rem;
            font-weight: 800;
            margin-bottom: 10px;
            letter-spacing: -0.025em;
        }

        .hero p {
            font-size: 1.125rem;
            opacity: 0.9;
            max-width: 600px;
            margin: 0 auto;
        }

        /* Conteúdo */
        .main-content {
            padding: 40px 0;
            flex: 1;
        }

        .section-title {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-main);
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .section-title i {
            color: var(--secondary);
            font-size: 1.2rem;
        }

        /* Cards Grid */
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 24px;
            margin-bottom: 40px;
        }

        .card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 24px;
            transition: all 0.2s ease;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
            border-color: var(--primary);
        }

        /* Estilização dos Endpoints */
        .method-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: white;
            margin-bottom: 12px;
        }

        .method-get { background-color: var(--method-get); }
        .method-post { background-color: var(--method-post); }

        .endpoint-path {
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.95rem;
            color: var(--text-main);
            background-color: #f3f4f6;
            padding: 6px 10px;
            border-radius: 6px;
            display: inline-block;
            margin-bottom: 12px;
            word-break: break-all;
        }

        .card h3 {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 8px;
            color: var(--text-main);
        }

        .card p {
            font-size: 0.9rem;
            color: var(--text-muted);
        }

        /* Quick Links */
        .link-card {
            text-decoration: none;
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            border-top: 4px solid var(--primary);
        }

        .link-card i {
            font-size: 2rem;
            color: var(--primary);
            margin-bottom: 12px;
        }

        .link-card span {
            font-weight: 600;
            color: var(--text-main);
        }

        /* Features */
        .feature-card {
            border-left: 4px solid var(--secondary);
        }
        
        .feature-card i {
            font-size: 1.5rem;
            color: var(--secondary);
            margin-bottom: 15px;
        }

        /* Code Block */
        .code-block {
            background-color: #1e293b; /* slate-800 */
            color: #e2e8f0;
            padding: 20px;
            border-radius: 8px;
            font-family: 'Consolas', monospace;
            font-size: 0.9rem;
            overflow-x: auto;
            margin-top: 15px;
            border: 1px solid #334155;
        }

        .note-box {
            background-color: #eff6ff; /* blue-50 */
            border: 1px solid #bfdbfe;
            border-radius: 8px;
            padding: 20px;
        }

        /* Footer */
        .footer {
            background-color: var(--bg-card);
            border-top: 1px solid var(--border-color);
            padding: 30px 0;
            text-align: center;
            color: var(--text-muted);
            font-size: 0.9rem;
        }

        /* Responsividade */
        @media (max-width: 768px) {
            .hero h1 { font-size: 1.8rem; }
            .grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="wrapper">
        <nav class="navbar">
            <div class="container nav-content">
                <div class="brand">
                    <i class="fas fa-chart-pie"></i>
                    <span>SAD-UEPR API</span>
                </div>
                </div>
        </nav>

        <header class="hero">
            <div class="container">
                <h1>Integração IPCA & Transparência</h1>
                <p>API oficial para correção monetária de contratos e análise de dados públicos do Paraná.</p>
            </div>
        </header>

        <main class="main-content">
            <div class="container">
                
                <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));">
                    <a href="api/docs" class="card link-card">
                        <i class="fas fa-book-open"></i>
                        <h3>Swagger UI</h3>
                        <p>Documentação interativa</p>
                    </a>
                    <a href="/api/redoc" class="card link-card">
                        <i class="fas fa-file-code"></i>
                        <h3>ReDoc</h3>
                        <p>Especificação técnica detalhada</p>
                    </a>
                    <a href="/api/transparencia/status" class="card link-card">
                        <i class="fas fa-heartbeat"></i>
                        <h3>Health Check</h3>
                        <p>Monitoramento de status da API</p>
                    </a>
                </div>

                <h2 class="section-title"><i class="fas fa-network-wired"></i> Endpoints Principais</h2>
                
                <div class="grid">
                    <div class="card">
                        <div style="display:flex; justify-content:space-between; align-items:start;">
                            <span class="method-badge method-get">GET</span>
                        </div>
                        <div class="endpoint-path">/ipca/corrigir</div>
                        <h3>Correção Monetária</h3>
                        <p>Calcula a correção de valores monetários entre duas datas utilizando o índice acumulado do IPCA.</p>
                    </div>

                    <div class="card">
                        <div style="display:flex; justify-content:space-between; align-items:start;">
                            <span class="method-badge method-get">GET</span>
                        </div>
                        <div class="endpoint-path">/ipca/filtro</div>
                        <h3>Consulta Histórica</h3>
                        <p>Retorna dados brutos e tratados do IPCA filtrados por mês e ano específicos.</p>
                    </div>

                    <div class="card">
                        <div style="display:flex; justify-content:space-between; align-items:start;">
                            <span class="method-badge method-post">POST</span>
                        </div>
                        <div class="endpoint-path">/transparencia/consultar</div>
                        <h3>Crawler Transparência</h3>
                        <p>Executa o crawler no Portal da Transparência PR e aplica correção automática aos valores encontrados.</p>
                    </div>
                </div>

                <div class="grid" style="grid-template-columns: 1fr 1fr;">
                    
                    <div>
                        <h2 class="section-title"><i class="fas fa-layer-group"></i> Recursos</h2>
                        <div style="display: flex; flex-direction: column; gap: 15px;">
                            <div class="card feature-card">
                                <i class="fas fa-database"></i>
                                <h3>Fonte Oficial (IPEA)</h3>
                                <p>Sincronização direta com dados governamentais.</p>
                            </div>
                            <div class="card feature-card">
                                <i class="fas fa-sync-alt"></i>
                                <h3>Processamento Assíncrono</h3>
                                <p>Alta performance para consultas de múltiplos anos.</p>
                            </div>
                        </div>
                    </div>

                    <div>
                        <h2 class="section-title"><i class="fas fa-terminal"></i> Como Integrar</h2>
                        <div class="card">
                            <p>Exemplo de requisição para crawler com correção:</p>
                            <div class="code-block">
curl -X POST "http://url:8000/transparencia/consultar" \\
-H "Content-Type: application/json" \\
-d '{
  "data_inicio": "01/2020",
  "data_fim": "03/2022"
}'
                            </div>
                            <p style="margin-top: 15px; font-size: 0.85rem; color: var(--secondary);">
                                <i class="fas fa-info-circle"></i> O retorno incluirá os valores originais e corrigidos para a data atual.
                            </p>
                        </div>
                    </div>
                </div>

            </div>
        </main>

        <footer class="footer">
            <div class="container">
                <p>&copy; 2025 SAD-UEPR. Todos os direitos reservados.</p>
                <p style="margin-top: 5px; font-size: 0.8rem; opacity: 0.7;">Desenvolvido com FastAPI e React</p>
            </div>
        </footer>
    </div>
</body>
</html>
"""