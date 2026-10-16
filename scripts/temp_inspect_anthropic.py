import sys
import anthropic

print('python', sys.executable)
print('anthropic file:', anthropic.__file__)
print('anthropic version:', getattr(anthropic, '__version__', 'unknown'))
print('anthropic dir sample:', [name for name in dir(anthropic) if name.lower() in ['asyncanthropic','client','models','anthropic']])
print('AsyncAnthropic has attrs:', [name for name in dir(anthropic.AsyncAnthropic) if 'model' in name.lower() or 'message' in name.lower()][:50])
