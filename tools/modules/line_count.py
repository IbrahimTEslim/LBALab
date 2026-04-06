import os

modules_dir = '.'
for filename in sorted(os.listdir(modules_dir)):
    if filename.endswith('.py') and filename != '__init__.py':
        filepath = os.path.join(modules_dir, filename)
        with open(filepath, 'r') as f:
            lines = len(f.readlines())
            status = 'OK' if lines <= 250 else f'TOO LONG ({lines} lines)'
            print(f'{filename}: {lines} lines - {status}')
