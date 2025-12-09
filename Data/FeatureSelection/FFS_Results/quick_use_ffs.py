
# ============================================================
# SCRIPT DE USO RÁPIDO - MODELO FFS
# ============================================================
import joblib
import pandas as pd
import numpy as np

# Carregar modelo FFS
ffs_data = joblib.load('../../Data/FeatureSelection/FFS_Results/ridge_model_ffs.pkl')
model = ffs_data['pipeline']
selected_features = ffs_data['selected_features']
log_params = ffs_data['log_params']

# Função para fazer predições
def predict_with_ffs_model(X_new):
    """
    Faz predições com o modelo FFS

    Parameters:
    -----------
    X_new : DataFrame
        Novos dados (deve conter as features selecionadas)

    Returns:
    --------
    y_pred_linear : array
        Predições na escala linear
    y_pred_log : array
        Predições na escala log
    """
    # Verificar se todas as features selecionadas estão presentes
    missing_features = set(selected_features) - set(X_new.columns)
    if missing_features:
        raise ValueError(f"Features faltando: {missing_features}")

    # Selecionar apenas as features necessárias
    X_selected = X_new[selected_features]

    # Fazer predição (na escala log)
    y_pred_log = model.predict(X_selected)

    # Converter para escala linear
    y_pred_linear = np.exp(y_pred_log * log_params['inv_mult']) - 1

    return y_pred_linear, y_pred_log

# Função para obter importância das features
def get_feature_importance():
    """Retorna a importância das features do modelo FFS"""
    return ffs_data['feature_importance']

# Exemplo de uso
if __name__ == "__main__":
    print("Modelo FFS carregado!")
    print(f"Número de features selecionadas: {len(selected_features)}")
    print(f"Features: {selected_features[:5]}...")  # Mostrar apenas as 5 primeiras
    print(f"R² Score do modelo FFS: {ffs_data['best_score']:.4f}")

    # Exemplo de predição (requer dados de entrada)
    # X_example = pd.DataFrame(...)  # Seus dados aqui
    # y_linear, y_log = predict_with_ffs_model(X_example)
