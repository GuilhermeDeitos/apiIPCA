import pytest
import json
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, mock_open
from app.utils.ipca_cache import IPCACache, ipca_cache


@pytest.fixture
def temp_cache_path(tmp_path):
    """Cria caminho temporário para cache em testes."""
    cache_file = tmp_path / "test_series_ipca.json"
    return cache_file


@pytest.fixture
def cache_instance(temp_cache_path):
    """Cria instância de cache para testes."""
    return IPCACache(cache_path=temp_cache_path)


@pytest.fixture
def dados_ipca_mock():
    """Dados IPCA mock para testes."""
    return {
        "01/2020": 100.0,
        "02/2020": 101.5,
        "03/2020": 102.0,
        "01/2021": 110.0,
        "02/2021": 111.5,
        "12/2023": 120.0
    }


class TestIPCACacheInicializacao:
    """Testes para inicialização do cache."""
    
    def test_inicializacao_padrao(self):
        """Testa inicialização com caminho padrão."""
        cache = IPCACache()
        
        assert cache.cache_path is not None
        assert "series_ipca.json" in str(cache.cache_path)
    
    def test_inicializacao_customizada(self, temp_cache_path):
        """Testa inicialização com caminho customizado."""
        cache = IPCACache(cache_path=temp_cache_path)
        
        assert cache.cache_path == temp_cache_path
    
    def test_ensure_cache_dir_cria_diretorio(self, temp_cache_path):
        """Testa que diretório é criado se não existir."""
        # Garantir que diretório não existe
        if temp_cache_path.parent.exists():
            temp_cache_path.parent.rmdir()
        
        cache = IPCACache(cache_path=temp_cache_path)
        
        assert temp_cache_path.parent.exists()


class TestIPCACacheCarregar:
    """Testes para carregar cache."""
    
    def test_carregar_cache_arquivo_nao_existe(self, cache_instance):
        """Testa carregar quando arquivo não existe."""
        resultado = cache_instance.carregar_cache()
        
        assert resultado is None
    
    def test_carregar_cache_sucesso(self, cache_instance, dados_ipca_mock):
        """Testa carregamento bem-sucedido."""
        # Preparar cache no disco
        cache_data = {
            "ultima_atualizacao": datetime.now().isoformat(),
            "total_registros": len(dados_ipca_mock),
            "dados": dados_ipca_mock
        }
        
        with open(cache_instance.cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f)
        
        # Carregar
        resultado = cache_instance.carregar_cache()
        
        assert resultado is not None
        assert resultado["dados"] == dados_ipca_mock
        assert resultado["total_registros"] == len(dados_ipca_mock)
    
    def test_carregar_cache_json_invalido(self, cache_instance):
        """Testa tratamento de JSON inválido."""
        # Escrever JSON inválido
        with open(cache_instance.cache_path, 'w') as f:
            f.write("{ invalid json }")
        
        resultado = cache_instance.carregar_cache()
        
        assert resultado is None
    
    def test_carregar_cache_arquivo_corrompido(self, cache_instance):
        """Testa tratamento de arquivo corrompido."""
        with open(cache_instance.cache_path, 'w') as f:
            f.write("não é json")
        
        resultado = cache_instance.carregar_cache()
        
        assert resultado is None


class TestIPCACacheSalvar:
    """Testes para salvar cache."""
    
    def test_salvar_cache_sucesso(self, cache_instance, dados_ipca_mock):
        """Testa salvamento bem-sucedido."""
        info = "Dados de teste"
        
        resultado = cache_instance.salvar_cache(dados_ipca_mock, info)
        
        assert resultado is True
        assert cache_instance.cache_path.exists()
        
        # Verificar conteúdo
        with open(cache_instance.cache_path, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        assert cache_data["dados"] == dados_ipca_mock
        assert cache_data["total_registros"] == len(dados_ipca_mock)
        assert cache_data["info"] == info
        assert "ultima_atualizacao" in cache_data
    
    def test_salvar_cache_vazio(self, cache_instance):
        """Testa que não salva cache vazio."""
        resultado = cache_instance.salvar_cache({}, "Info")
        
        assert resultado is False
        assert not cache_instance.cache_path.exists()
    
    def test_salvar_cache_extrai_metadados(self, cache_instance, dados_ipca_mock):
        """Testa extração de metadados."""
        cache_instance.salvar_cache(dados_ipca_mock, "Info")
        
        with open(cache_instance.cache_path, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        assert "anos_disponiveis" in cache_data
        assert 2020 in cache_data["anos_disponiveis"]
        assert 2021 in cache_data["anos_disponiveis"]
        assert 2023 in cache_data["anos_disponiveis"]
        
        assert cache_data["periodo_inicio"] == "2020"
        assert cache_data["periodo_fim"] == "2023"
        assert cache_data["ultimo_periodo"] == "12/2023"
    
    def test_salvar_cache_nao_sobrescreve_identico(self, cache_instance, dados_ipca_mock):
        """Testa que não salva se dados são idênticos."""
        # Salvar primeira vez
        cache_instance.salvar_cache(dados_ipca_mock, "Info")
        
        # Obter timestamp
        primeira_modificacao = cache_instance.cache_path.stat().st_mtime
        
        # Tentar salvar novamente (sem forçar)
        resultado = cache_instance.salvar_cache(dados_ipca_mock, "Info", forcar=False)
        
        # Deve retornar True mas não modificar arquivo
        assert resultado is True
        segunda_modificacao = cache_instance.cache_path.stat().st_mtime
        
        # Timestamp deve ser o mesmo (arquivo não foi modificado)
        # Nota: pode haver diferença mínima por arredondamento
        assert abs(primeira_modificacao - segunda_modificacao) < 0.1
    
    def test_salvar_cache_forcar_sobrescreve(self, cache_instance, dados_ipca_mock):
        """Testa que forçar sobrescreve mesmo com dados idênticos."""
        import time
        
        # Salvar primeira vez
        cache_instance.salvar_cache(dados_ipca_mock, "Info v1")
        time.sleep(0.1)  # Pequeno delay para garantir timestamp diferente
        
        # Salvar novamente forçando
        resultado = cache_instance.salvar_cache(dados_ipca_mock, "Info v2", forcar=True)
        
        assert resultado is True
        
        # Verificar que info foi atualizada
        with open(cache_instance.cache_path, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        assert cache_data["info"] == "Info v2"


class TestIPCACacheVerificarAtualizacao:
    """Testes para verificar necessidade de atualização."""
    
    def test_verificar_cache_nao_existe(self, cache_instance):
        """Testa quando cache não existe."""
        precisa, motivo = cache_instance.verificar_atualizacao_necessaria()
        
        assert precisa is True
        assert "não existe" in motivo.lower()
    
    def test_verificar_cache_vazio(self, cache_instance):
        """Testa quando cache existe mas está vazio."""
        cache_data = {
            "ultima_atualizacao": datetime.now().isoformat(),
            "dados": {}
        }
        
        with open(cache_instance.cache_path, 'w') as f:
            json.dump(cache_data, f)
        
        precisa, motivo = cache_instance.verificar_atualizacao_necessaria()
        
        assert precisa is True
        assert "vazio" in motivo.lower()
    
    def test_verificar_cache_desatualizado_30_dias(self, cache_instance, dados_ipca_mock):
        """Testa quando cache tem mais de 30 dias."""
        # Cache de 35 dias atrás
        data_antiga = datetime.now() - timedelta(days=35)
        
        cache_data = {
            "ultima_atualizacao": data_antiga.isoformat(),
            "dados": dados_ipca_mock
        }
        
        with open(cache_instance.cache_path, 'w') as f:
            json.dump(cache_data, f)
        
        precisa, motivo = cache_instance.verificar_atualizacao_necessaria()
        
        assert precisa is True
        assert "desatualizado" in motivo.lower()
        assert "35" in motivo
    
    def test_verificar_cache_atualizado_recente(self, cache_instance, dados_ipca_mock):
        """Testa quando cache está atualizado (menos de 30 dias)."""
        hoje = datetime.now()
        
        # para não cair na regra de "início do mês - verificar novos dados"
        if hoje.day <= 5:
            # Usar uma data do mesmo mês (por exemplo, dia 1 do mês atual)
            data_recente = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            # Fora do início do mês, usar 10 dias atrás está ok
            data_recente = hoje - timedelta(days=10)
        
        cache_data = {
            "ultima_atualizacao": data_recente.isoformat(),
            "dados": dados_ipca_mock
        }
        
        with open(cache_instance.cache_path, 'w') as f:
            json.dump(cache_data, f)
        
        precisa, motivo = cache_instance.verificar_atualizacao_necessaria()
        
        assert precisa is False
        assert "atualizado" in motivo.lower()
    
    def test_verificar_inicio_mes_atualizar(self, cache_instance, dados_ipca_mock):
        """Testa atualização no início do mês."""
        hoje = datetime.now()
        
        # Se estamos nos primeiros 5 dias do mês
        if hoje.day <= 5:
            # Cache do mês anterior
            mes_anterior = hoje.replace(day=1) - timedelta(days=1)
            
            cache_data = {
                "ultima_atualizacao": mes_anterior.isoformat(),
                "dados": dados_ipca_mock
            }
            
            with open(cache_instance.cache_path, 'w') as f:
                json.dump(cache_data, f)
            
            precisa, motivo = cache_instance.verificar_atualizacao_necessaria()
            
            assert precisa is True
            assert "início do mês" in motivo.lower()
    
    def test_verificar_data_invalida(self, cache_instance, dados_ipca_mock):
        """Testa tratamento de data inválida."""
        cache_data = {
            "ultima_atualizacao": "data-invalida",
            "dados": dados_ipca_mock
        }
        
        with open(cache_instance.cache_path, 'w') as f:
            json.dump(cache_data, f)
        
        precisa, motivo = cache_instance.verificar_atualizacao_necessaria()
        
        assert precisa is True
        assert "erro" in motivo.lower()


class TestIPCACacheOutrasOperacoes:
    """Testes para outras operações do cache."""
    
    def test_obter_ultimo_periodo(self, cache_instance, dados_ipca_mock):
        """Testa obtenção do último período."""
        cache_instance.salvar_cache(dados_ipca_mock, "Info")
        
        ultimo = cache_instance.obter_ultimo_periodo()
        
        assert ultimo == "12/2023"
    
    def test_obter_ultimo_periodo_cache_nao_existe(self, cache_instance):
        """Testa quando cache não existe."""
        ultimo = cache_instance.obter_ultimo_periodo()
        
        assert ultimo is None
    
    def test_limpar_cache_sucesso(self, cache_instance, dados_ipca_mock):
        """Testa limpeza de cache."""
        cache_instance.salvar_cache(dados_ipca_mock, "Info")
        assert cache_instance.cache_path.exists()
        
        resultado = cache_instance.limpar_cache()
        
        assert resultado is True
        assert not cache_instance.cache_path.exists()
    
    def test_limpar_cache_nao_existe(self, cache_instance):
        """Testa limpar quando cache não existe."""
        resultado = cache_instance.limpar_cache()
        
        assert resultado is False
    
    def test_obter_estatisticas_cache_existe(self, cache_instance, dados_ipca_mock):
        """Testa estatísticas com cache existente."""
        cache_instance.salvar_cache(dados_ipca_mock, "Info de teste")
        
        stats = cache_instance.obter_estatisticas()
        
        assert stats["existe"] is True
        assert stats["total_registros"] == len(dados_ipca_mock)
        assert 2020 in stats["anos_disponiveis"]
        assert "2020-2023" in stats["periodo"]
        assert stats["ultimo_periodo"] == "12/2023"
        assert "ultima_atualizacao" in stats
        assert stats["tamanho_arquivo_kb"] > 0
        assert str(cache_instance.cache_path) in stats["caminho"]
    
    def test_obter_estatisticas_cache_nao_existe(self, cache_instance):
        """Testa estatísticas quando cache não existe."""
        stats = cache_instance.obter_estatisticas()
        
        assert stats["existe"] is False
        assert stats["total_registros"] == 0
        assert stats["ultima_atualizacao"] is None
        assert stats["tamanho_arquivo"] == 0


class TestIPCACacheThreadSafety:
    """Testes para thread safety."""
    
    def test_lock_usado_em_carregar(self, cache_instance, mocker):
        """Testa que lock é usado ao carregar."""
        mock_lock = mocker.patch("app.utils.ipca_cache.cache_lock")
        
        cache_instance.carregar_cache()
        
        mock_lock.__enter__.assert_called()
    
    def test_lock_usado_em_salvar(self, cache_instance, dados_ipca_mock, mocker):
        """Testa que lock é usado ao salvar."""
        mock_lock = mocker.patch("app.utils.ipca_cache.cache_lock")
        
        cache_instance.salvar_cache(dados_ipca_mock, "Info")
        
        mock_lock.__enter__.assert_called()
    
    def test_lock_usado_em_limpar(self, cache_instance, mocker):
        """Testa que lock é usado ao limpar."""
        mock_lock = mocker.patch("app.utils.ipca_cache.cache_lock")
        
        cache_instance.limpar_cache()
        
        mock_lock.__enter__.assert_called()


class TestIPCACacheInstanciaGlobal:
    """Testes para instância global."""
    
    def test_instancia_global_existe(self):
        """Testa que instância global está disponível."""
        assert ipca_cache is not None
        assert isinstance(ipca_cache, IPCACache)
    
    def test_instancia_global_usa_caminho_padrao(self):
        """Testa que instância global usa caminho padrão."""
        assert "series_ipca.json" in str(ipca_cache.cache_path)