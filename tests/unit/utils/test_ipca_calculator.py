import pytest
from unittest.mock import Mock
from datetime import datetime
from app.utils.ipca_calculator import IPCACalculator, MonetaryCorrector, CAMPOS_MONETARIOS


class TestIPCACalculatorDeterminarPeriodoBase:
    """Testes para determinação do período base."""
    
    def test_determinar_periodo_base_com_referencia_fornecida(self):
        """Testa quando ipca_referencia é fornecido."""
        # Arrange
        ipca_service_mock = Mock()
        calculator = IPCACalculator(ipca_service_mock)
        
        # Act
        periodo = calculator.determinar_periodo_base("12/2023", "mensal")
        
        # Assert
        assert periodo == "12/2023"
    
    def test_determinar_periodo_base_mensal_sem_referencia(self):
        """Testa período base mensal quando não há referência."""
        # Arrange
        ipca_service_mock = Mock()
        calculator = IPCACalculator(ipca_service_mock)
        
        # Act
        periodo = calculator.determinar_periodo_base(None, "mensal")
        
        # Assert
        # Deve retornar mês/ano atual
        hoje = datetime.now()
        assert periodo == f"{hoje.month:02d}/{hoje.year}"
    
    def test_determinar_periodo_base_anual_sem_referencia(self):
        """Testa período base anual quando não há referência."""
        # Arrange
        ipca_service_mock = Mock()
        calculator = IPCACalculator(ipca_service_mock)
        
        # Act
        periodo = calculator.determinar_periodo_base(None, "anual")
        
        # Assert
        # Deve retornar ano atual
        hoje = datetime.now()
        assert periodo == str(hoje.year)


class TestIPCACalculatorObterIPCABase:
    """Testes para obtenção do IPCA base."""
    
    def test_obter_ipca_base_mensal(self):
        """Testa obtenção de IPCA base mensal."""
        # Arrange
        ipca_service_mock = Mock()
        ipca_service_mock.obter_ipca_por_periodo.return_value = 120.0
        calculator = IPCACalculator(ipca_service_mock)
        
        # Act
        ipca_base = calculator.obter_ipca_base("12/2023", "mensal")
        
        # Assert
        assert ipca_base == 120.0
        ipca_service_mock.obter_ipca_por_periodo.assert_called_once_with("12", "2023")
    
    def test_obter_ipca_base_anual(self):
        """Testa obtenção de IPCA base anual (média)."""
        # Arrange
        ipca_service_mock = Mock()
        ipca_service_mock.calcular_media_anual.return_value = 115.5
        calculator = IPCACalculator(ipca_service_mock)
        
        # Act
        ipca_base = calculator.obter_ipca_base("2023", "anual")
        
        # Assert
        assert ipca_base == 115.5
        ipca_service_mock.calcular_media_anual.assert_called_once_with("2023")
    
    def test_obter_ipca_base_anual_com_mes_no_periodo(self):
        """Testa quando período anual contém mês (deve extrair apenas ano)."""
        # Arrange
        ipca_service_mock = Mock()
        ipca_service_mock.calcular_media_anual.return_value = 115.5
        calculator = IPCACalculator(ipca_service_mock)
        
        # Act
        ipca_base = calculator.obter_ipca_base("12/2023", "anual")
        
        # Assert
        assert ipca_base == 115.5
        ipca_service_mock.calcular_media_anual.assert_called_once_with("2023")
    
    def test_obter_ipca_base_erro_ipca_nao_encontrado(self):
        """Testa erro quando IPCA não é encontrado."""
        # Arrange
        ipca_service_mock = Mock()
        ipca_service_mock.obter_ipca_por_periodo.side_effect = ValueError("IPCA não encontrado")
        calculator = IPCACalculator(ipca_service_mock)
        
        # Act & Assert
        with pytest.raises(Exception, match="Não foi possível obter o IPCA de referência"):
            calculator.obter_ipca_base("13/2023", "mensal")


class TestIPCACalculatorCalcularIPCAsAnuais:
    """Testes para cálculo de IPCAs médios anuais."""
    
    def test_calcular_ipcas_anuais_multiplos_anos(self):
        """Testa cálculo para múltiplos anos."""
        # Arrange
        ipca_service_mock = Mock()
        ipca_service_mock.calcular_media_anual.side_effect = [110.0, 115.0, 120.0]
        calculator = IPCACalculator(ipca_service_mock)
        
        periodos_por_ano = {
            "2020": {1, 2, 3},
            "2021": {1, 2, 3, 4, 5, 6},
            "2022": {1, 2}
        }
        
        # Act
        resultado = calculator.calcular_ipcas_anuais(periodos_por_ano)
        
        # Assert
        assert len(resultado) == 3
        assert resultado["2020"] == 110.0
        assert resultado["2021"] == 115.0
        assert resultado["2022"] == 120.0
    
    def test_calcular_ipcas_anuais_ano_sem_meses(self):
        """Testa quando ano não tem meses."""
        # Arrange
        ipca_service_mock = Mock()
        calculator = IPCACalculator(ipca_service_mock)
        
        periodos_por_ano = {"2020": set()}  # Sem meses
        
        # Act
        resultado = calculator.calcular_ipcas_anuais(periodos_por_ano)
        
        # Assert
        assert len(resultado) == 0


class TestMonetaryCorrectorProcessarCorrecaoDados:
    """Testes para processamento de correção monetária."""
    
    @pytest.fixture
    def ipca_calculator_mock(self):
        """Mock do IPCACalculator."""
        ipca_service = Mock()
        ipca_service.obter_ipca_por_periodo.return_value = 100.0
        ipca_service.calcular_media_anual.return_value = 110.0
        ipca_service.converter_valor_monetario_string.side_effect = lambda v: float(str(v).replace(".", "").replace(",", "."))
        ipca_service.formatar_valor_brasileiro.side_effect = lambda v: f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        return IPCACalculator(ipca_service)
    
    def test_processar_correcao_mensal_sucesso(self, ipca_calculator_mock):
        """Testa correção monetária mensal."""
        # Arrange
        corrector = MonetaryCorrector(ipca_calculator_mock)
        dados = [
            {
                "UNIDADE_ORCAMENTARIA": "UEL",
                "MES": "1",
                "ANO": "2020",
                "ORCAMENTO_INICIAL_LOA": "1000000"
            }
        ]
        
        # Act
        dados_corrigidos, dados_nao_processados = corrector.processar_correcao_dados(
            dados,
            ipca_base=120.0,
            periodo_base="12/2023",
            tipo_correcao="mensal",
            ano_contexto=2020
        )
        
        # Assert
        assert len(dados_corrigidos) == 1
        assert len(dados_nao_processados) == 0
        assert "_correcao_aplicada" in dados_corrigidos[0]
        assert dados_corrigidos[0]["_correcao_aplicada"]["fator_correcao"] == pytest.approx(1.2, abs=0.01)
    
    def test_processar_correcao_sem_campos_monetarios(self, ipca_calculator_mock):
        """Testa dados sem campos monetários."""
        # Arrange
        corrector = MonetaryCorrector(ipca_calculator_mock)
        dados = [
            {
                "UNIDADE_ORCAMENTARIA": "UEL",
                "MES": "1",
                "ANO": "2020"
                # Sem campos monetários
            }
        ]
        
        # Act
        dados_corrigidos, dados_nao_processados = corrector.processar_correcao_dados(
            dados,
            ipca_base=120.0,
            periodo_base="12/2023",
            tipo_correcao="mensal",
            ano_contexto=2020
        )
        
        # Assert
        assert len(dados_corrigidos) == 0
        assert len(dados_nao_processados) == 1
        assert "Nenhum campo monetário válido" in dados_nao_processados[0]["motivo"]
    
    def test_processar_correcao_ano_invalido(self, ipca_calculator_mock):
        """Testa dados com ano inválido."""
        # Arrange
        corrector = MonetaryCorrector(ipca_calculator_mock)
        dados = [
            {
                "UNIDADE_ORCAMENTARIA": "UEL",
                "MES": "1",
                # ANO ausente
                "ORCAMENTO_INICIAL_LOA": "1000000"
            }
        ]
        
        # Act
        dados_corrigidos, dados_nao_processados = corrector.processar_correcao_dados(
            dados,
            ipca_base=120.0,
            periodo_base="12/2023",
            tipo_correcao="mensal"
            # Sem ano_contexto
        )
        
        # Assert
        assert len(dados_corrigidos) == 0
        assert len(dados_nao_processados) == 1
        assert "Ano inválido" in dados_nao_processados[0]["motivo"]