enum AppEnvironment { dev, stage, prod }

AppEnvironment appEnvironmentFromDefine() {
  const env = String.fromEnvironment('TORE_ENV', defaultValue: 'dev');
  switch (env.toLowerCase()) {
    case 'prod':
      return AppEnvironment.prod;
    case 'stage':
      return AppEnvironment.stage;
    default:
      return AppEnvironment.dev;
  }
}

String appEnvironmentLabel(AppEnvironment value) => value.name.toUpperCase();
