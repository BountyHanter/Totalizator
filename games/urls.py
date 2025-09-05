from django.urls import path, include

from games.views.bet import PlaceBetView
from games.views.payout import PayoutCategoryListView
from games.views.rounds import CurrentRoundView, CurrentRoundPoolView, RoundHistoryView, \
    LastBetVariantsView, RoundStatsView, MyVariantsInRoundView
from games.views.wins import BiggestWinView, TopWinningVariantsView, MyWinCouponView

urlpatterns = [
    path("biggest-win/", BiggestWinView.as_view()),
    path("top_10_win/", TopWinningVariantsView.as_view()),
    path("payout-categories/", PayoutCategoryListView.as_view()),
    path('current_round/', include([
        path('', CurrentRoundView.as_view()),
        path('pool/', CurrentRoundPoolView.as_view()),
    ])),
    path('variants/', LastBetVariantsView.as_view()),
    path('history/', RoundHistoryView.as_view()),

    path("<int:pk>/stats/", RoundStatsView.as_view()),

    path("<int:pk>/my-variants/", MyVariantsInRoundView.as_view()),

    path('bet/', PlaceBetView.as_view()),

    path('my-win-coupon/', MyWinCouponView.as_view()),

]
