import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestFluxoCompletoIPCA:
    """Testes E2E para fluxo completo de consulta IPCA."""
    
    def test_fluxo_consulta_e_correcao_valor(self):
        """
        Testa fluxo completo:
        1. Listar todos os dados IPCA
        2. Consultar IPCA de um período específico
        3. Corrigir um valor monetário
        """
        # Step 1: Obter todos os dados IPCA
        response = client.get("/ipca")
        assert response.status_code == 200
        dados_ipca = response.json()
        assert "data" in dados_ipca
        assert len(dados_ipca["data"]) > 0
        
        # Step 2: Selecionar uma data existente para consulta
        primeira_data = list(dados_ipca["data"].keys())[0]
        mes, ano = primeira_data.split("/")
        
        response = client.get(f"/ipca/filtro?mes={mes}&ano={ano}")
        assert response.status_code == 200
        ipca_especifico = response.json()
        assert ipca_especifico["data"] == primeira_data
        assert "valor" in ipca_especifico
        
        # Step 3: Corrigir um valor usando datas válidas
        # Selecionar duas datas para correção
        datas_disponiveis = list(dados_ipca["data"].keys())
        if len(datas_disponiveis) >= 2:
            data_inicial = datas_disponiveis[0]
            data_final = datas_disponiveis[-1]
            
            mes_inicial, ano_inicial = data_inicial.split("/")
            mes_final, ano_final = data_final.split("/")
            
            response = client.get(
                f"/ipca/corrigir?valor=1000&mes_inicial={mes_inicial}&ano_inicial={ano_inicial}"
                f"&mes_final={mes_final}&ano_final={ano_final}"
            )
            assert response.status_code == 200
            correcao = response.json()
            assert "valor_corrigido" in correcao
            assert correcao["valor_inicial"] == 1000.0
    
    def test_fluxo_calculo_media_anual(self):
        """
        Testa fluxo completo:
        1. Listar dados IPCA
        2. Calcular média anual de um ano
        3. Calcular médias de múltiplos anos
        """
        # Step 1: Obter dados
        response = client.get("/ipca")
        assert response.status_code == 200
        dados = response.json()
        
        # Step 2: Extrair anos disponíveis
        anos = set()
        for data in dados["data"].keys():
            _, ano = data.split("/")
            anos.add(ano)
        
        if anos:
            # Step 3: Calcular média de um ano
            ano_escolhido = list(anos)[0]
            response = client.get(f"/ipca/media-anual/{ano_escolhido}")
            assert response.status_code == 200
            media_anual = response.json()
            assert media_anual["ano"] == ano_escolhido
            assert "media_ipca" in media_anual
            
            # Step 4: Calcular médias de múltiplos anos
            anos_query = "&".join([f"anos={ano}" for ano in list(anos)[:3]])
            response = client.get(f"/ipca/medias-anuais?{anos_query}")
            assert response.status_code == 200
            medias = response.json()
            assert len(medias) > 0


class TestFluxoErrosERecuperacao:
    """Testes E2E para cenários de erro e recuperação."""
    
    def test_fluxo_erro_404_e_tentativa_valida(self):
        """
        Testa fluxo:
        1. Tentar consultar data inexistente (404)
        2. Consultar data válida (200)
        """
        # Step 1: Tentar data inexistente
        response = client.get("/ipca/filtro?mes=13&ano=2020")
        assert response.status_code == 404
        
        # Step 2: Consultar todos os dados para encontrar uma data válida
        response = client.get("/ipca")
        assert response.status_code == 200
        dados = response.json()
        
        # Step 3: Usar primeira data válida
        primeira_data = list(dados["data"].keys())[0]
        mes, ano = primeira_data.split("/")
        
        response = client.get(f"/ipca/filtro?mes={mes}&ano={ano}")
        assert response.status_code == 200
    
    def test_fluxo_validacao_parametros(self):
        """
        Testa validação de parâmetros em múltiplos endpoints.
        """
        # Teste 1: Valor negativo para correção
        response = client.get(
            "/ipca/corrigir?valor=-1000&mes_inicial=01&ano_inicial=2020"
            "&mes_final=12&ano_final=2023"
        )
        assert response.status_code == 400
        
        # Teste 2: Parâmetros faltando
        response = client.get("/ipca/filtro")
        assert response.status_code == 422
        
        # Teste 3: Média anual de ano sem dados
        response = client.get("/ipca/media-anual/2050")
        assert response.status_code == 404