import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock
from app.main import app
from app.services.ipca_service import get_ipca_service, IPCAService

client = TestClient(app)


@pytest.fixture
def mock_ipca_service():
    """Cria mock do serviço IPCA."""
    mock = Mock(spec=IPCAService)
    
    # Dados mock
    mock_dados = {
        "01/2020": 100.0,
        "02/2020": 101.5,
        "03/2020": 102.0,
        "12/2023": 120.0
    }
    
    mock.obter_todos_dados = Mock(return_value={
        "info": "Mock",
        "data": mock_dados
    })
    
    # ✅ Mock dinâmico para obter_valor_por_data
    def obter_valor_por_data_side_effect(mes: str, ano: str):
        data_key = f"{mes}/{ano}"
        if data_key in mock_dados:
            return {"data": data_key, "valor": mock_dados[data_key]}
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Data não encontrada")
    
    mock.obter_valor_por_data = Mock(side_effect=obter_valor_por_data_side_effect)
    
    #  Mock dinâmico para corrigir_valor que respeita os parâmetros
    def corrigir_valor_side_effect(valor: float, mes_inicial: str, ano_inicial: str, 
                                   mes_final: str, ano_final: str):
        from fastapi import HTTPException
        
        data_inicial = f"{mes_inicial}/{ano_inicial}"
        data_final = f"{mes_final}/{ano_final}"
        
        # Validar se datas existem
        if data_inicial not in mock_dados or data_final not in mock_dados:
            raise HTTPException(
                status_code=404, 
                detail="IPCA para data inicial ou final não encontrado"
            )
        
        # Validar valor
        if valor < 0:
            raise HTTPException(
                status_code=400,
                detail="O valor a ser corrigido não pode ser negativo"
            )
        
        # Calcular correção com os dados mock
        indice_inicial = mock_dados[data_inicial]
        indice_final = mock_dados[data_final]
        
        valor_corrigido = valor * (indice_final / indice_inicial)
        percentual = ((indice_final / indice_inicial) - 1) * 100
        
        return {
            "valor_inicial": valor,
            "data_inicial": data_inicial,
            "data_final": data_final,
            "indice_ipca_inicial": indice_inicial,
            "indice_ipca_final": indice_final,
            "valor_corrigido": round(valor_corrigido, 2),
            "percentual_correcao": round(percentual, 4)
        }
    
    mock.corrigir_valor = Mock(side_effect=corrigir_valor_side_effect)
    
    # ✅ Mock dinâmico para obter_media_anual
    def obter_media_anual_side_effect(ano: str, meses=None):
        from fastapi import HTTPException
        
        if meses is None:
            meses = list(range(1, 13))
        
        valores = []
        valores_mensais = {}
        meses_disponiveis = []
        
        for mes in meses:
            periodo = f"{mes:02d}/{ano}"
            if periodo in mock_dados:
                valor = mock_dados[periodo]
                valores.append(valor)
                valores_mensais[f"{mes:02d}"] = valor
                meses_disponiveis.append(f"{mes:02d}")
        
        if not valores:
            raise HTTPException(
                status_code=404,
                detail=f"Nenhum valor IPCA encontrado para o ano {ano}"
            )
        
        media = sum(valores) / len(valores)
        
        return {
            "ano": ano,
            "media_ipca": round(media, 4),
            "total_meses": len(valores),
            "meses_disponiveis": meses_disponiveis,
            "valores_mensais": valores_mensais
        }
    
    mock.obter_media_anual = Mock(side_effect=obter_media_anual_side_effect)
    
    # ✅ Mock dinâmico para obter_medias_multiplos_anos
    def obter_medias_multiplos_anos_side_effect(anos, meses=None):
        resultado = {}
        for ano in anos:
            try:
                resultado[ano] = obter_media_anual_side_effect(ano, meses)
            except:
                resultado[ano] = {"erro": f"Dados não disponíveis para {ano}"}
        return resultado
    
    mock.obter_medias_multiplos_anos = Mock(side_effect=obter_medias_multiplos_anos_side_effect)
    
    return mock


@pytest.fixture(autouse=True)
def setup_mock_service(mock_ipca_service):
    """Configura mock do serviço para todos os testes."""
    # ✅ Resetar singleton e limpar overrides
    IPCAService.reset_instance()
    app.dependency_overrides.clear()
    
    # Configurar override
    app.dependency_overrides[get_ipca_service] = lambda: mock_ipca_service
    
    yield
    
    # Limpar após testes
    app.dependency_overrides.clear()
    IPCAService.reset_instance()


class TestFluxoCompletoIPCA:
    """Testes E2E para fluxo completo de consulta IPCA."""
    
    def test_fluxo_consulta_e_correcao_valor(self):
        """Testa fluxo completo de consulta e correção."""
        # 1. Obter todos os dados
        response = client.get("/ipca")
        assert response.status_code == 200
        dados_ipca = response.json()
        assert "data" in dados_ipca
        assert len(dados_ipca["data"]) > 0
        
        # 2. Consultar valor específico
        response = client.get("/ipca/filtro?mes=01&ano=2020")
        assert response.status_code == 200
        dados_mes = response.json()
        assert dados_mes["data"] == "01/2020"
        assert dados_mes["valor"] == 100.0
        
        # 3. Corrigir valor
        response = client.get(
            "/ipca/corrigir?valor=1000&mes_inicial=01&ano_inicial=2020"
            "&mes_final=12&ano_final=2023"
        )
        assert response.status_code == 200
        correcao = response.json()
        assert correcao["valor_inicial"] == 1000.0
        assert correcao["valor_corrigido"] == 1200.0  # 1000 * (120/100)
        assert correcao["percentual_correcao"] == 20.0
    
    def test_fluxo_historico_periodo(self):
        """Testa consulta de histórico."""
        response = client.get("/ipca")
        assert response.status_code == 200
        dados = response.json()
        
        # Extrair anos disponíveis
        anos = set()
        for data in dados["data"].keys():
            _, ano = data.split("/")
            anos.add(ano)
        
        if anos:
            ano_escolhido = list(anos)[0]
            response = client.get(f"/ipca/media-anual/{ano_escolhido}")
            assert response.status_code == 200
            media = response.json()
            assert "ano" in media
            assert "media_ipca" in media


class TestFluxoErrosERecuperacao:
    """Testes de cenários de erro."""
    
    def test_fluxo_erro_400_validacao(self):
        """Testa validação de entrada inválida."""
        # Mês inválido
        response = client.get("/ipca/filtro?mes=13&ano=2020")
        assert response.status_code == 400
        
        # Consulta válida
        response = client.get("/ipca/filtro?mes=01&ano=2020")
        assert response.status_code == 200
    
    def test_fluxo_validacao_parametros(self):
        """Testa validação de parâmetros."""
        # Valor negativo
        response = client.get(
            "/ipca/corrigir?valor=-1000&mes_inicial=01&ano_inicial=2020"
            "&mes_final=12&ano_final=2023"
        )
        assert response.status_code == 400
        
        # Valor válido
        response = client.get(
            "/ipca/corrigir?valor=1000&mes_inicial=01&ano_inicial=2020"
            "&mes_final=12&ano_final=2023"
        )
        assert response.status_code == 200
    
    def test_fluxo_data_nao_encontrada(self):
        """Testa consulta de data inexistente."""
        response = client.get("/ipca/filtro?mes=01&ano=2050")
        assert response.status_code == 404


class TestFluxoPerformance:
    """Testes de performance."""
    
    def test_fluxo_multiplas_consultas(self):
        """Testa múltiplas consultas."""
        for _ in range(10):
            response = client.get("/ipca")
            assert response.status_code == 200
            
            response = client.get("/ipca/filtro?mes=01&ano=2020")
            assert response.status_code == 200


class TestFluxoIntegracaoCompleta:
    """Testes de integração completa."""
    
    def test_fluxo_usuario_real_completo(self):
        """Testa fluxo completo de usuário."""
        # 1. Verificar disponibilidade do serviço
        response = client.get("/ipca")
        assert response.status_code == 200
        dados = response.json()
        assert "data" in dados
        
        # 2. Consultar valor inicial (01/2020)
        response = client.get("/ipca/filtro?mes=01&ano=2020")
        assert response.status_code == 200
        valor_inicial = response.json()
        assert valor_inicial["valor"] == 100.0
        
        # 3. Consultar valor final (12/2023)
        response = client.get("/ipca/filtro?mes=12&ano=2023")
        assert response.status_code == 200
        valor_final = response.json()
        assert valor_final["valor"] == 120.0
        
        # 4. Corrigir valor de R$ 5.000,00
        response = client.get(
            "/ipca/corrigir?valor=5000&mes_inicial=01&ano_inicial=2020"
            "&mes_final=12&ano_final=2023"
        )
        assert response.status_code == 200
        resultado = response.json()
        
        #  Verificar que o valor inicial é realmente 5000
        assert resultado["valor_inicial"] == 5000.0
        
        # Verificar cálculo: 5000 * (120/100) = 6000
        assert resultado["valor_corrigido"] == 6000.0
        
        # Verificar percentual: ((120/100) - 1) * 100 = 20%
        assert resultado["percentual_correcao"] == 20.0
        
        # 5. Obter média anual de 2020
        response = client.get("/ipca/media-anual/2020")
        assert response.status_code == 200
        media = response.json()
        assert media["ano"] == "2020"
        assert media["total_meses"] == 3  # Temos dados para 01, 02, 03/2020
        assert "media_ipca" in media
    
    def test_fluxo_multiplos_valores_correcao(self):
        """Testa correção de múltiplos valores."""
        valores_teste = [100.0, 1000.0, 5000.0, 10000.0]
        
        for valor in valores_teste:
            response = client.get(
                f"/ipca/corrigir?valor={valor}&mes_inicial=01&ano_inicial=2020"
                "&mes_final=12&ano_final=2023"
            )
            assert response.status_code == 200
            resultado = response.json()
            
            # Verificar que o valor inicial corresponde ao enviado
            assert resultado["valor_inicial"] == valor
            
            # Verificar que o valor corrigido é maior (pois houve inflação)
            assert resultado["valor_corrigido"] > valor
            
            # Verificar cálculo: valor * (120/100) = valor * 1.2
            assert resultado["valor_corrigido"] == round(valor * 1.2, 2)
            
class TestFluxoCacheIPCA:
    """Testes E2E para fluxo de cache."""
    
    def test_fluxo_completo_cache(self, mocker):
        """Testa fluxo completo de gerenciamento de cache."""
        # Arrange
        mock_stats_inicial = {"existe": False, "total_registros": 0}
        mock_stats_apos = {"existe": True, "total_registros": 200}
        
        #  Mockar no local de origem (carregar_ipca)
        mocker.patch(
            "app.utils.carregar_ipca.obter_estatisticas_cache",
            side_effect=[mock_stats_inicial, mock_stats_apos]
        )
        mocker.patch(
            "app.utils.carregar_ipca.forcar_atualizacao_cache",
            return_value=(True, "Cache atualizado")
        )
        
        # Act & Assert
        
        # 1. Verificar status inicial (sem cache)
        response = client.get("/ipca/cache/status")
        assert response.status_code == 200
        assert response.json()["existe"] is False
        
        # 2. Forçar atualização do cache
        response = client.post("/ipca/cache/atualizar")
        assert response.status_code == 200
        assert "sucesso" in response.json()["status"]
        
        # 3. Verificar status após atualização
        response = client.get("/ipca/cache/status")
        assert response.status_code == 200
        assert response.json()["existe"] is True