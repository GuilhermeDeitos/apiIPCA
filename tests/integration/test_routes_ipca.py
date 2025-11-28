import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock
from app.main import app
from app.services.ipca_service import IPCAService, get_ipca_service

#  MUDANÇA: Adicionar fixture para resetar singleton


@pytest.fixture(autouse=True)
def reset_ipca_singleton():
    """Reseta o singleton do IPCAService antes de cada teste."""
    IPCAService.reset_instance()
    yield
    IPCAService.reset_instance()


@pytest.fixture
def mock_ipca_service():
    """Mock do serviço IPCA para testes de integração."""
    mock_dados = {
        "01/2020": 100.0,
        "02/2020": 101.5,
        "12/2023": 120.0
    }
    # Adicionar dados completos para 2020 e 2023
    for mes in range(1, 13):
        mock_dados[f"{mes:02d}/2020"] = 100.0 + mes * 0.5
        mock_dados[f"{mes:02d}/2023"] = 115.0 + mes
    
    # Criar mock do serviço
    mock_service = Mock(spec=IPCAService)
    mock_service._ipca_dict = mock_dados
    mock_service._ipca_info = "Dados mockados para testes"
    mock_service._dados_disponiveis = True
    
    # Mock dos métodos principais
    mock_service.verificar_disponibilidade = Mock()
    
    mock_service.obter_todos_dados = Mock(return_value={
        "info": mock_service._ipca_info,
        "data": mock_service._ipca_dict
    })
    
    mock_service.obter_status_servico = Mock(return_value={
        "status": "sucesso",
        "dados_disponiveis": True,
        "total_registros": len(mock_dados),
        "mensagem": mock_service._ipca_info,
        "circuit_breaker": {
            "state": "CLOSED",
            "failures": 0,
            "last_failure": None,
            "next_attempt_in": 0
        }
    })
    
    def obter_valor_por_data_side_effect(mes: str, ano: str):
        from fastapi import HTTPException
        data_key = f"{mes}/{ano}"
        if data_key in mock_dados:
            return {"data": data_key, "valor": mock_dados[data_key]}
        else:
            raise HTTPException(status_code=404, detail="Data não encontrada")
    
    mock_service.obter_valor_por_data = Mock(side_effect=obter_valor_por_data_side_effect)
    
    def obter_media_anual_side_effect(ano: str, meses=None):
        from fastapi import HTTPException
        
        if meses is None:
            meses = list(range(1, 13))
        
        valores = []
        valores_mensais = {}
        
        for mes in meses:
            periodo = f"{mes:02d}/{ano}"
            if periodo in mock_dados:
                valor = mock_dados[periodo]
                valores.append(valor)
                valores_mensais[f"{mes:02d}"] = valor
        
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
            "meses_disponiveis": list(valores_mensais.keys()),
            "valores_mensais": valores_mensais
        }
    
    mock_service.obter_media_anual = Mock(side_effect=obter_media_anual_side_effect)
    
    def obter_medias_multiplos_anos_side_effect(anos, meses=None):
        resultado = {}
        for ano in anos:
            try:
                resultado[ano] = obter_media_anual_side_effect(ano, meses)
            except:
                resultado[ano] = {"erro": f"Dados não disponíveis para {ano}"}
        return resultado
    
    mock_service.obter_medias_multiplos_anos = Mock(side_effect=obter_medias_multiplos_anos_side_effect)
    
    def corrigir_valor_side_effect(valor, mes_inicial, ano_inicial, mes_final, ano_final):
        from fastapi import HTTPException
        
        data_inicial = f"{mes_inicial}/{ano_inicial}"
        data_final = f"{mes_final}/{ano_final}"
        
        if data_inicial not in mock_dados or data_final not in mock_dados:
            raise HTTPException(
                status_code=404,
                detail="IPCA para data inicial ou final não encontrado"
            )
        
        if valor < 0:
            raise HTTPException(
                status_code=400,
                detail="O valor a ser corrigido não pode ser negativo"
            )
        
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
    
    mock_service.corrigir_valor = Mock(side_effect=corrigir_valor_side_effect)
    
    return mock_service


@pytest.fixture
def client(mock_ipca_service):
    """ Criar client APÓS configurar override."""
    # Limpar overrides anteriores
    app.dependency_overrides.clear()
    
    #  MUDANÇA: Resetar singleton ANTES de configurar override
    IPCAService.reset_instance()
    
    # Configurar override do serviço
    app.dependency_overrides[get_ipca_service] = lambda: mock_ipca_service
    
    # Criar client DEPOIS do override
    test_client = TestClient(app)
    
    yield test_client
    
    # Limpar overrides após teste
    app.dependency_overrides.clear()
    IPCAService.reset_instance()


def test_listar_rotas_disponiveis(client):
    """Lista todas as rotas disponíveis na aplicação."""
    routes = []
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            methods = ', '.join(route.methods) if route.methods else 'N/A'
            routes.append(f"{methods:10} {route.path}")
    
    print("\n=== ROTAS DISPONÍVEIS ===")
    for route in sorted(routes):
        print(route)


class TestIPCARoutesIntegracao:
    """Testes de integração para os endpoints de IPCA."""
    
    def test_get_ipca_todos_dados_sucesso(self, client):
        """Testa endpoint GET /ipca para obter todos os dados."""
        response = client.get("/ipca")
        
        assert response.status_code == 200
        data = response.json()
        assert "info" in data
        assert "data" in data
        assert isinstance(data["data"], dict)
        assert len(data["data"]) > 0
    
    def test_get_ipca_status(self, client):
        """Testa endpoint GET /ipca/status."""
        response = client.get("/ipca/status")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["dados_disponiveis"] is True
    
    def test_get_ipca_por_data_sucesso(self, client):
        """Testa endpoint GET /ipca/filtro?mes=01&ano=2020."""
        response = client.get("/ipca/filtro?mes=01&ano=2020")
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"] == "01/2020"
        assert "valor" in data
    
    def test_get_ipca_por_data_nao_encontrada(self, client):
        """Testa endpoint GET /ipca/filtro com data inexistente."""
        response = client.get("/ipca/filtro?mes=01&ano=2050")
        
        assert response.status_code == 404
    
    def test_get_ipca_media_anual_sucesso(self, client, mock_ipca_service):
        """Testa endpoint GET /ipca/media-anual/2023."""
        # DEBUG: Verificar configuração do mock
        meses_2023 = [k for k in mock_ipca_service._ipca_dict.keys() if k.endswith('/2023')]
        print(f"\n=== DEBUG: Mock configurado com {len(meses_2023)} meses para 2023")
        print(f"=== DEBUG: Meses disponíveis: {sorted(meses_2023)}")
        
        # Verificar se side_effect está funcionando corretamente
        resultado_mock = mock_ipca_service.obter_media_anual("2023", meses=None)
        print(f"=== DEBUG: Mock direto retorna total_meses={resultado_mock['total_meses']}")
        
        #  MUDANÇA: Verificar qual serviço está sendo usado
        from app.routes.ipca import get_service
        servico_usado = get_service()
        print(f"=== DEBUG: Tipo do serviço: {type(servico_usado)}, ID: {id(servico_usado)}")
        print(f"=== DEBUG: É mock? {servico_usado is mock_ipca_service}")
        
        response = client.get("/ipca/media-anual/2023")
        
        assert response.status_code == 200
        data = response.json()
        print(f"=== DEBUG: Resposta API total_meses={data['total_meses']}, meses={data.get('meses_disponiveis', [])}")
        
        assert data["ano"] == "2023"
        assert data["total_meses"] == 12, f"Esperado 12 meses mas recebeu {data['total_meses']}"
        assert len(data["meses_disponiveis"]) == 12
    
    def test_get_ipca_media_anual_ano_sem_dados(self, client):
        """Testa endpoint GET /ipca/media-anual/2050 para ano sem dados."""
        response = client.get("/ipca/media-anual/2050")
        
        assert response.status_code == 404
    
    def test_get_ipca_medias_multiplos_anos_sucesso(self, client):
        """Testa endpoint GET /ipca/medias-anuais?anos=2020&anos=2023."""
        response = client.get("/ipca/medias-anuais?anos=2020&anos=2023")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "2020" in data
        assert "2023" in data
    
    def test_get_ipca_corrigir_valor_sucesso(self, client):
        """Testa endpoint GET /ipca/corrigir."""
        response = client.get(
            "/ipca/corrigir"
            "?valor=1000.0"
            "&mes_inicial=01"
            "&ano_inicial=2020"
            "&mes_final=12"
            "&ano_final=2023"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["valor_inicial"] == 1000.0
        assert data["valor_corrigido"] > data["valor_inicial"]
    
    def test_get_ipca_corrigir_valor_negativo(self, client):
        """Testa endpoint GET /ipca/corrigir com valor negativo."""
        response = client.get(
            "/ipca/corrigir"
            "?valor=-1000.0"
            "&mes_inicial=01"
            "&ano_inicial=2020"
            "&mes_final=12"
            "&ano_final=2023"
        )
        
        assert response.status_code == 400


class TestIPCARoutesValidacao:
    """Testes de validação de entrada."""
    
    def test_get_ipca_corrigir_sem_parametros(self, client):
        """Testa GET /ipca/corrigir sem parâmetros obrigatórios."""
        response = client.get("/ipca/corrigir?valor=1000.0")
        
        assert response.status_code == 422


class TestIPCARoutesErros:
    """Testes para cenários de erro."""
    
    def test_get_ipca_servico_indisponivel(self):
        """Testa endpoint quando serviço está indisponível."""
        from fastapi import HTTPException
        
        #  MUDANÇA: Resetar singleton e criar mock ANTES de criar client
        IPCAService.reset_instance()
        app.dependency_overrides.clear()
        
        mock_indisponivel = Mock(spec=IPCAService)
        #  MUDANÇA: side_effect deve ser uma função que lança a exceção
        def raise_http_exception(*args, **kwargs):
            raise HTTPException(status_code=503, detail="Serviço indisponível")
        
        mock_indisponivel.obter_todos_dados = Mock(side_effect=raise_http_exception)
        mock_indisponivel.verificar_disponibilidade = Mock()
        
        # Reconfigurar override
        app.dependency_overrides[get_ipca_service] = lambda: mock_indisponivel
        
        # Criar novo client APÓS override
        test_client = TestClient(app)
        
        try:
            response = test_client.get("/ipca")
            print(f"=== DEBUG: Status code recebido: {response.status_code}")
            if response.status_code == 200:
                print(f"=== DEBUG: Resposta: {response.json()}")
            else:
                print(f"=== DEBUG: Resposta: {response.text}")
            
            assert response.status_code == 503, f"Esperado 503 mas recebeu {response.status_code}"
        finally:
            app.dependency_overrides.clear()
            IPCAService.reset_instance()
    
    def test_get_ipca_status_servico_indisponivel(self):
        """Testa status quando serviço está indisponível."""
        #  MUDANÇA: Resetar singleton
        IPCAService.reset_instance()
        app.dependency_overrides.clear()
        
        # Criar novo mock para status de erro
        mock_indisponivel = Mock(spec=IPCAService)
        mock_indisponivel.obter_status_servico = Mock(return_value={
            "status": "erro",
            "dados_disponiveis": False,
            "total_registros": 0,
            "mensagem": "Erro ao carregar dados"
        })
        
        # Reconfigurar override
        app.dependency_overrides[get_ipca_service] = lambda: mock_indisponivel
        
        # Criar novo client APÓS override
        test_client = TestClient(app)
        
        try:
            response = test_client.get("/ipca/status")
            assert response.status_code == 200
            
            data = response.json()
            print(f"=== DEBUG: Status recebido: {data}")
            assert data["status"] == "erro", f"Esperado 'erro' mas recebeu '{data['status']}'"
            assert data["dados_disponiveis"] is False
        finally:
            app.dependency_overrides.clear()
            IPCAService.reset_instance()
            
class TestIPCACacheRoutes:
    """Testes para endpoints de gerenciamento de cache."""
    
    def test_get_cache_status_sucesso(self, client, mocker):
        """Testa endpoint GET /ipca/cache/status."""
        # Arrange
        mock_stats = {
            "existe": True,
            "total_registros": 150,
            "anos_disponiveis": [2020, 2021, 2022],
            "periodo": "2020-2023",
            "ultimo_periodo": "12/2023",
            "ultima_atualizacao": "2024-11-28T10:00:00",
            "tamanho_arquivo_kb": 25.5,
            "caminho": "/data/series_ipca.json"
        }
        
        # Mockar no local de origem (carregar_ipca)
        mocker.patch(
            "app.utils.carregar_ipca.obter_estatisticas_cache",
            return_value=mock_stats
        )
        
        # Act
        response = client.get("/ipca/cache/status")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["existe"] is True
        assert data["total_registros"] == 150
        assert 2020 in data["anos_disponiveis"]
    
    def test_get_cache_status_cache_nao_existe(self, client, mocker):
        """Testa status quando cache não existe."""
        # Arrange
        mock_stats = {
            "existe": False,
            "total_registros": 0,
            "ultima_atualizacao": None,
            "tamanho_arquivo": 0
        }
        
        # Mockar no local de origem
        mocker.patch(
            "app.utils.carregar_ipca.obter_estatisticas_cache",
            return_value=mock_stats
        )
        
        # Act
        response = client.get("/ipca/cache/status")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["existe"] is False
        assert data["total_registros"] == 0
    
    def test_post_atualizar_cache_sucesso(self, client, mocker):
        """Testa endpoint POST /ipca/cache/atualizar."""
        # Arrange
        # Mockar no local de origem
        mocker.patch(
            "app.utils.carregar_ipca.forcar_atualizacao_cache",
            return_value=(True, "Cache atualizado com 200 registros")
        )
        
        # Act
        response = client.post("/ipca/cache/atualizar")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sucesso"
        assert "200 registros" in data["mensagem"]
    
    def test_post_atualizar_cache_falha(self, client, mocker):
        """Testa atualização de cache com falha."""
        # Arrange
        # Mockar no local de origem
        mocker.patch(
            "app.utils.carregar_ipca.forcar_atualizacao_cache",
            return_value=(False, "Erro ao conectar com API")
        )
        
        # Act
        response = client.post("/ipca/cache/atualizar")
        
        # Assert
        assert response.status_code == 500
        assert "Erro ao conectar" in response.json()["detail"]
    
    def test_cache_status_erro_interno(self, client, mocker):
        """Testa tratamento de erro interno ao obter status."""
        # Arrange
        # Mockar no local de origem
        mocker.patch(
            "app.utils.carregar_ipca.obter_estatisticas_cache",
            side_effect=Exception("Erro inesperado")
        )
        
        # Act
        response = client.get("/ipca/cache/status")
        
        # Assert
        assert response.status_code == 500
        assert "Erro ao obter status do cache" in response.json()["detail"]