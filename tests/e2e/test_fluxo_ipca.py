import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestFluxoCompletoIPCA:
    """Testes E2E para fluxo completo de consulta IPCA."""
    
    def test_fluxo_consulta_e_correcao_valor(self, mocker):
        """
        Testa fluxo completo:
        1. Listar todos os dados IPCA
        2. Consultar IPCA de um período específico
        3. Corrigir um valor monetário
        """
        mock_dados_ipca = {
            "01/2020": 100.0,
            "02/2020": 101.5,
            "03/2020": 102.0,
            "12/2023": 120.0
        }
        
        mocker.patch(
            'app.routes.ipca.ipca_service.obter_todos_dados',
            return_value={"info": "Mock", "data": mock_dados_ipca}
        )
        
        mocker.patch(
            'app.routes.ipca.ipca_service.obter_valor_por_data',
            return_value={"data": "01/2020", "valor": 100.0}
        )
        
        mocker.patch(
            'app.routes.ipca.ipca_service.corrigir_valor',
            return_value={
                "valor_inicial": 1000.0,
                "valor_corrigido": 1200.0,
                "percentual_correcao": 20.0,
                "data_inicial": "01/2020",
                "data_final": "12/2023",
                "indice_ipca_inicial": 100.0,
                "indice_ipca_final": 120.0
            }
        )
        
        response = client.get("/ipca")
        assert response.status_code == 200
        dados_ipca = response.json()
        assert "data" in dados_ipca
        assert len(dados_ipca["data"]) > 0
        
        response = client.get("/ipca/filtro?mes=01&ano=2020")
        assert response.status_code == 200
        dados_mes = response.json()
        assert dados_mes["data"] == "01/2020"
        assert "valor" in dados_mes
        
        response = client.get(
            "/ipca/corrigir?valor=1000&mes_inicial=01&ano_inicial=2020"
            "&mes_final=12&ano_final=2023"
        )
        assert response.status_code == 200
        correcao = response.json()
        assert "valor_inicial" in correcao
        assert "valor_corrigido" in correcao
        assert correcao["valor_inicial"] == 1000.0
        assert correcao["valor_corrigido"] > 1000.0
    
    def test_fluxo_historico_periodo(self, mocker):
        """Testa consulta de histórico de período específico."""
        mock_historico = {
            "01/2020": 100.0,
            "02/2020": 101.5,
            "03/2020": 102.0
        }
        
        mocker.patch(
            'app.routes.ipca.ipca_service.obter_todos_dados',
            return_value={"info": "Mock", "data": mock_historico}
        )
        
        response = client.get("/ipca")
        
        assert response.status_code == 200
        dados = response.json()
        assert len(dados["data"]) == 3


class TestFluxoErrosERecuperacao:
    """Testa tratamento de erros e recuperação."""
    
    def test_fluxo_erro_400_validacao_e_tentativa_valida(self, mocker):
        """
        Testa fluxo:
        1. Tentar consultar data com validação inválida (400)
        2. Consultar data válida (200)
        """
        # Step 1: Tentar mês inválido (validação retorna 400)
        response = client.get("/ipca/filtro?mes=13&ano=2020")
        assert response.status_code == 400
        assert "Mês deve estar entre 01 e 12" in response.json()["detail"]
        
        # Step 2: Mock de dados válidos
        mock_dados_ipca = {
            "01/2020": 100.0,
            "02/2020": 101.5
        }
        
        mocker.patch(
            'app.routes.ipca.ipca_service.obter_todos_dados',
            return_value={"info": "Mock", "data": mock_dados_ipca}
        )
        
        mocker.patch(
            'app.routes.ipca.ipca_service.obter_valor_por_data',
            return_value={"data": "01/2020", "valor": 100.0}
        )
        
        # Step 3: Consultar data válida
        response = client.get("/ipca/filtro?mes=01&ano=2020")
        assert response.status_code == 200
    
    def test_fluxo_validacao_parametros(self, mocker):
        """Testa validação de parâmetros em múltiplos endpoints."""
        from fastapi import HTTPException
        
        def mock_corrigir_valor(valor: float, mes_inicial: str, ano_inicial: str, 
                                mes_final: str, ano_final: str):
            if valor < 0:
                raise HTTPException(status_code=400, detail="Valor não pode ser negativo")
            return {
                "valor_inicial": valor,
                "valor_corrigido": valor * 1.15,
                "percentual_correcao": 15.0,
                "data_inicial": f"{mes_inicial}/{ano_inicial}",
                "data_final": f"{mes_final}/{ano_final}",
                "indice_ipca_inicial": 100.0,
                "indice_ipca_final": 115.0
            }
        
        mocker.patch(
            'app.routes.ipca.ipca_service.corrigir_valor',
            side_effect=mock_corrigir_valor
        )
        
        # Teste 1: Valor negativo
        response = client.get(
            "/ipca/corrigir?valor=-1000&mes_inicial=01&ano_inicial=2020"
            "&mes_final=12&ano_final=2023"
        )
        assert response.status_code == 400
        
        # Teste 2: Mês inválido (validação retorna 400)
        response = client.get("/ipca/filtro?mes=13&ano=2020")
        assert response.status_code == 400
        
        # Teste 3: Parâmetros faltando
        response = client.get("/ipca/filtro?mes=01")
        assert response.status_code == 422
        
        # Teste 4: Valor válido deve funcionar
        response = client.get(
            "/ipca/corrigir?valor=1000&mes_inicial=01&ano_inicial=2020"
            "&mes_final=12&ano_final=2023"
        )
        assert response.status_code == 200
    
    def test_fluxo_dados_inconsistentes(self, mocker):
        """Testa tratamento quando dados estão inconsistentes."""
        mocker.patch(
            'app.routes.ipca.ipca_service.obter_todos_dados',
            return_value={"info": "Sem dados", "data": {}}
        )
        
        response = client.get("/ipca")
        assert response.status_code == 200
        dados = response.json()
        assert "data" in dados
        assert len(dados["data"]) == 0


class TestFluxoPerformance:
    """Testa performance e limites do sistema."""
    
    def test_fluxo_multiplas_consultas_simultaneas(self, mocker):
        """Simula múltiplas consultas para verificar estabilidade."""
        mock_dados = {
            "01/2020": 100.0,
            "02/2020": 101.5,
            "03/2020": 102.0
        }
        
        mocker.patch(
            'app.routes.ipca.ipca_service.obter_todos_dados',
            return_value={"info": "Mock", "data": mock_dados}
        )
        
        for _ in range(10):
            response = client.get("/ipca")
            assert response.status_code == 200
            assert "data" in response.json()
    
    def test_fluxo_correcao_valores_extremos(self, mocker):
        """Testa correção com valores muito grandes e muito pequenos."""
        from fastapi import HTTPException
        
        def mock_corrigir_valor(valor: float, mes_inicial: str, ano_inicial: str,
                                mes_final: str, ano_final: str):
            if valor < 0:
                raise HTTPException(status_code=400, detail="Valor não pode ser negativo")
            if valor > 999999999:
                raise HTTPException(status_code=400, detail="Valor muito grande")
            
            return {
                "valor_inicial": valor,
                "valor_corrigido": valor * 1.15,
                "percentual_correcao": 15.0,
                "data_inicial": f"{mes_inicial}/{ano_inicial}",
                "data_final": f"{mes_final}/{ano_final}",
                "indice_ipca_inicial": 100.0,
                "indice_ipca_final": 115.0
            }
        
        mocker.patch(
            'app.routes.ipca.ipca_service.corrigir_valor',
            side_effect=mock_corrigir_valor
        )
        
        # Valor pequeno
        response = client.get(
            "/ipca/corrigir?valor=0.01&mes_inicial=01&ano_inicial=2020"
            "&mes_final=12&ano_final=2023"
        )
        assert response.status_code == 200
        
        # Valor grande mas válido
        response = client.get(
            "/ipca/corrigir?valor=1000000&mes_inicial=01&ano_inicial=2020"
            "&mes_final=12&ano_final=2023"
        )
        assert response.status_code == 200
        
        # Valor muito grande
        response = client.get(
            "/ipca/corrigir?valor=9999999999&mes_inicial=01&ano_inicial=2020"
            "&mes_final=12&ano_final=2023"
        )
        assert response.status_code == 400


class TestFluxoIntegracaoCompleta:
    """Testes de integração end-to-end completos."""
    
    def test_fluxo_usuario_real_completo(self, mocker):
        """
        Simula fluxo completo de um usuário real:
        1. Listar dados disponíveis
        2. Escolher período
        3. Fazer correção
        4. Validar resultado
        """
        mock_dados = {
            "01/2020": 100.0,
            "12/2023": 120.0
        }
        
        mock_correcao = {
            "valor_inicial": 5000.0,
            "valor_corrigido": 6000.0,
            "percentual_correcao": 20.0,
            "data_inicial": "01/2020",
            "data_final": "12/2023",
            "indice_ipca_inicial": 100.0,
            "indice_ipca_final": 120.0
        }
        
        mocker.patch(
            'app.routes.ipca.ipca_service.obter_todos_dados',
            return_value={"info": "Mock", "data": mock_dados}
        )
        mocker.patch(
            'app.routes.ipca.ipca_service.corrigir_valor',
            return_value=mock_correcao
        )
        
        response = client.get("/ipca")
        assert response.status_code == 200
        dados = response.json()
        assert len(dados["data"]) > 0
        
        response = client.get(
            "/ipca/corrigir?valor=5000&mes_inicial=01&ano_inicial=2020"
            "&mes_final=12&ano_final=2023"
        )
        
        assert response.status_code == 200
        resultado = response.json()
        
        assert resultado["valor_inicial"] == 5000.0
        assert resultado["valor_corrigido"] > 5000.0
        assert resultado["percentual_correcao"] > 0
        
        diferenca = resultado["valor_corrigido"] - resultado["valor_inicial"]
        assert diferenca > 0
        assert resultado["data_inicial"] == "01/2020"
        assert resultado["data_final"] == "12/2023"