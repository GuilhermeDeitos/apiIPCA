import pytest
from app.utils.data_processor import DataExtractor, DataOrganizer


class TestDataExtractorExtrairAno:
    """Testes para extração de ano dos dados."""
    
    def test_extrair_ano_com_contexto(self):
        """Testa extração quando ano_contexto é fornecido (tem prioridade)."""
        # Arrange
        item = {"ANO": "2021", "MES": "01"}
        
        # Act
        ano = DataExtractor.extrair_ano(item, ano_contexto=2020)
        
        # Assert
        assert ano == "2020"  # Deve usar ano_contexto
    
    def test_extrair_ano_campo_ANO(self):
        """Testa extração do campo ANO."""
        # Arrange
        item = {"ANO": "2020", "MES": "01"}
        
        # Act
        ano = DataExtractor.extrair_ano(item)
        
        # Assert
        assert ano == "2020"
    
    def test_extrair_ano_campo_ano_minusculo(self):
        """Testa extração do campo 'ano' minúsculo."""
        # Arrange
        item = {"ano": "2020", "MES": "01"}
        
        # Act
        ano = DataExtractor.extrair_ano(item)
        
        # Assert
        assert ano == "2020"
    
    def test_extrair_ano_campo_ano_validado(self):
        """Testa extração do campo _ano_validado."""
        # Arrange
        item = {"_ano_validado": 2020, "MES": "01"}
        
        # Act
        ano = DataExtractor.extrair_ano(item)
        
        # Assert
        assert ano == "2020"
    
    def test_extrair_ano_sem_ano_retorna_none(self):
        """Testa quando não há campo de ano."""
        # Arrange
        item = {"MES": "01", "VALOR": "1000"}
        
        # Act
        ano = DataExtractor.extrair_ano(item)
        
        # Assert
        assert ano is None


class TestDataExtractorExtrairMes:
    """Testes para extração de mês dos dados."""
    
    def test_extrair_mes_campo_MES(self):
        """Testa extração do campo MES."""
        # Arrange
        item = {"ANO": "2020", "MES": "1"}
        
        # Act
        mes = DataExtractor.extrair_mes(item)
        
        # Assert
        assert mes == "01"  # Deve formatar com zero à esquerda
    
    def test_extrair_mes_ja_formatado(self):
        """Testa extração quando mês já está formatado."""
        # Arrange
        item = {"ANO": "2020", "MES": "12"}
        
        # Act
        mes = DataExtractor.extrair_mes(item)
        
        # Assert
        assert mes == "12"
    
    def test_extrair_mes_campo_mes_minusculo(self):
        """Testa extração do campo 'mes' minúsculo."""
        # Arrange
        item = {"ANO": "2020", "mes": "3"}
        
        # Act
        mes = DataExtractor.extrair_mes(item)
        
        # Assert
        assert mes == "03"
    
    def test_extrair_mes_sem_mes_retorna_padrao(self):
        """Testa quando não há campo de mês (retorna dezembro)."""
        # Arrange
        item = {"ANO": "2020", "VALOR": "1000"}
        
        # Act
        mes = DataExtractor.extrair_mes(item)
        
        # Assert
        assert mes == "12"  # Padrão: dezembro


class TestDataExtractorExtrairDadosResposta:
    """Testes para extração de dados da resposta da API."""
    
    def test_extrair_dados_campo_dados_por_ano(self):
        """Testa extração quando campo é 'dados_por_ano'."""
        # Arrange
        resposta = {
            "processamento": "sincrono",
            "dados_por_ano": {
                "2020": {"dados": [], "total_registros": 0}
            }
        }
        
        # Act
        dados = DataExtractor.extrair_dados_de_resposta(resposta)
        
        # Assert
        assert "2020" in dados
        assert dados["2020"]["total_registros"] == 0
    
    def test_extrair_dados_campo_dados_parciais_por_ano(self):
        """Testa extração quando campo é 'dados_parciais_por_ano'."""
        # Arrange
        resposta = {
            "status": "processando",
            "dados_parciais_por_ano": {
                "2020": {"dados": [], "total_registros": 50}
            }
        }
        
        # Act
        dados = DataExtractor.extrair_dados_de_resposta(resposta)
        
        # Assert
        assert "2020" in dados
        assert dados["2020"]["total_registros"] == 50
    
    def test_extrair_dados_sem_campo_retorna_vazio(self):
        """Testa quando não há dados na resposta."""
        # Arrange
        resposta = {"status": "erro", "mensagem": "Erro ao processar"}
        
        # Act
        dados = DataExtractor.extrair_dados_de_resposta(resposta)
        
        # Assert
        assert dados == {}


class TestDataOrganizerReorganizarPorAno:
    """Testes para reorganização de dados por ano."""
    
    def test_reorganizar_dados_estrutura_basica(self):
        """Testa reorganização básica."""
        # Arrange
        dados = [
            {"_ano_validado": 2020, "VALOR": "100"},
            {"_ano_validado": 2020, "VALOR": "200"},
            {"_ano_validado": 2021, "VALOR": "300"}
        ]
        
        # Act
        resultado = DataOrganizer.reorganizar_por_ano(dados)
        
        # Assert
        assert "2020" in resultado
        assert "2021" in resultado
        assert resultado["2020"]["total_registros"] == 2
        assert resultado["2021"]["total_registros"] == 1
    
    def test_reorganizar_dados_extrai_metadados_correcao(self):
        """Testa extração de metadados de correção."""
        # Arrange
        dados = [
            {
                "_ano_validado": 2020,
                "VALOR": "100",
                "_correcao_aplicada": {
                    "fator_correcao": 1.2,
                    "ipca_periodo": 100.0,
                    "ipca_referencia": 120.0,
                    "periodo_referencia": "12/2023",
                    "tipo_correcao": "mensal"
                }
            }
        ]
        
        # Act
        resultado = DataOrganizer.reorganizar_por_ano(dados)
        
        # Assert
        assert resultado["2020"]["fator_correcao"] == 1.2
        assert resultado["2020"]["tipo_correcao"] == "mensal"
        
        # Verificar que _correcao_aplicada foi removido dos dados
        assert "_correcao_aplicada" not in resultado["2020"]["dados"][0]
    
    def test_reorganizar_dados_ignora_anos_invalidos(self):
        """Testa que anos inválidos são ignorados."""
        # Arrange
        dados = [
            {"_ano_validado": 2020, "VALOR": "100"},
            {"VALOR": "200"},  # Sem ano
            {"ANO": "None", "VALOR": "300"}  # Ano inválido
        ]
        
        # Act
        resultado = DataOrganizer.reorganizar_por_ano(dados)
        
        # Assert
        assert len(resultado) == 1
        assert "2020" in resultado
        assert resultado["2020"]["total_registros"] == 1
    
    def test_reorganizar_dados_metadados_padrao(self):
        """Testa que metadados padrão são inicializados."""
        # Arrange
        dados = [{"_ano_validado": 2020, "VALOR": "100"}]
        
        # Act
        resultado = DataOrganizer.reorganizar_por_ano(dados)
        
        # Assert
        assert resultado["2020"]["fator_correcao"] is None
        assert resultado["2020"]["ipca_periodo"] is None
        assert resultado["2020"]["ipca_referencia"] is None
        assert resultado["2020"]["periodo_referencia"] is None
        assert resultado["2020"]["tipo_correcao"] is None