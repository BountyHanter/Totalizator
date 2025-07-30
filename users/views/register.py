from django.contrib import messages
from django.contrib.auth import login
from users.forms import UserCreationForm
from django.shortcuts import redirect, render


def register_view(request):
    if request.user.is_authenticated:
        return redirect('index')
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Регистрация прошла успешно!")
            return redirect('index')
    else:
        form = UserCreationForm()
    return render(request, 'games/register.html', {'form': form})