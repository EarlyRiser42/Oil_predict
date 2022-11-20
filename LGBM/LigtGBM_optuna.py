import optuna
from optuna.samplers import TPESampler
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import re
from sklearn.metrics import f1_score
from sklearn.preprocessing import LabelEncoder

def competition_metric(true, pred):
    return f1_score(true, pred, average="macro")


sampler = TPESampler(seed=10)
param = []


def objective(trial):
    train = pd.read_csv('../data/train.csv')

    new_names = {col: re.sub(r'[^A-Za-z0-9_]+', '', col) for col in train.columns}
    new_n_list = list(new_names.values())
    # [LightGBM] Feature appears more than one time.
    new_names = {col: f'{new_col}_{i}' if new_col in new_n_list[:i] else new_col for i, (col, new_col) in
                 enumerate(new_names.items())}
    train = train.rename(columns=new_names)

    categorical_features = ['COMPONENT_ARBITRARY', 'YEAR']
    # Inference(실제 진단 환경)에 사용하는 컬럼

    train = train.fillna(0)
    two_Y = train['Y_LABEL']
    all_X = train.drop(['ID', 'Y_LABEL'], axis=1)

    train_X, val_X, train_y, val_y = train_test_split(all_X, two_Y, test_size=0.2, random_state=42, stratify=two_Y)

    le = LabelEncoder()
    for col in categorical_features:
        train_X[col] = le.fit_transform(train_X[col])
        val_X[col] = le.transform(val_X[col])

    params = {}
    params['objective'] = 'binary'
    params["verbose"] = 1
    params['metric'] = 'binary_logloss'
    params['device_type'] = 'gpu'
    params['boosting_type'] = 'gbdt'
    params['learning_rate'] = trial.suggest_float("learning_rate", 0.001, 0.005)
    # 예측력 상승
    params['num_iterations'] = 5000
    params['min_child_samples'] = trial.suggest_int('min_child_samples', 100, 1000)
    params['n_estimators'] = trial.suggest_int('n_estimators',1000, 25000)
    params['num_leaves'] = trial.suggest_int('num_leaves', 1000, 25056)
    params['max_depth'] = trial.suggest_int('max_depth', 20, 60)
    # overfitting 방지
    params['min_child_weight'] = trial.suggest_float('min_child_weight', 0.01, 4)
    params['min_child_samples'] = trial.suggest_int('min_child_samples', 1, 50)
    params['bagging_fraction'] = trial.suggest_float('bagging_fraction', 0.6, 0.99)
    params['subsample_freq'] = trial.suggest_int('subsample_freq', 60, 99)
    params['lambda_l1'] = trial.suggest_float('lambda_l1', 0.01, 2)
    params['lambda_l2'] = trial.suggest_float('lambda_l2', 0.01, 2)
    params['min_gain_to_split'] = trial.suggest_float('min_gain_to_split', 0.001, 0.8)
    params['feature_fraction'] = trial.suggest_float('feature_fraction', 0.7, 0.99)

    # Generate model
    bst = lgb.LGBMClassifier(**params)
    bst.fit(train_X, train_y, eval_set=[(val_X, val_y)], eval_metric='binary_logloss', early_stopping_rounds=25)
    pred = bst.predict(val_X, num_iteration=bst.best_iteration_)
    f1_macro = competition_metric(val_y, pred)
    print('The f1_macro of prediction is:', f1_macro)
    return f1_macro


if __name__ == "__main__":
    study = optuna.create_study(direction="maximize", sampler=sampler)
    study.optimize(objective, n_trials=100)

    print("Number of finished trials: {}".format(len(study.trials)))

    print("Best trial:")
    trial = study.best_trial
    print("  Value: {}".format(trial.value))

    print("  Params: ")
    for key, value in trial.params.items():
        print("    {}: {}".format(key, value))
