from django.urls import path, include

from games.views.bet import PlaceBetView
from games.views.payout import PayoutCategoryListView
from games.views.rounds import CurrentRoundView, CurrentRoundPoolView, LastBetCouponsView, RoundHistoryView
from games.views.wins import BiggestWinView, TopWinningCouponsView

urlpatterns = [
    path("biggest-win/", BiggestWinView.as_view()),
    path("top_10_win/", TopWinningCouponsView.as_view()),
    path("payout-categories/", PayoutCategoryListView.as_view()),
    path('current_round/', include([
        path('', CurrentRoundView.as_view()),
        path('pool/', CurrentRoundPoolView.as_view()),
        path('coupons/', LastBetCouponsView.as_view()),

    ])),
    path('history/', RoundHistoryView.as_view()),

    path('bet/', PlaceBetView.as_view()),

]
