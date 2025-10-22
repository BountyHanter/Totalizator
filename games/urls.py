from django.urls import path, include

from games.views.bet import PlaceBetView
from games.views.fanpoints import FanPointsTableView
from games.views.fanpool import FanPoolAmountView
from games.views.last_result import TeamStatsView
from games.views.payout import PayoutSchemeListView
from games.views.playoff import FanVoteView, FanVoteCountView, PlayoffBracketView, NextPlayoffTimerView
from games.views.rounds import CurrentRoundView, RoundHistoryView, \
    LastBetVariantsView, RoundStatsView, MyVariantsInRoundView, MyVariantDetailView
from games.views.wins import BiggestWinView, TopWinningVariantsView, MyWinCouponView

urlpatterns = [
    path("biggest-win/", BiggestWinView.as_view()),
    path("top_10_win/", TopWinningVariantsView.as_view()),
    path("payout-categories/", PayoutSchemeListView.as_view()),
    path('current-round/', include([
        path('', CurrentRoundView.as_view()),

        path('my-variants/', MyVariantDetailView.as_view()),
    ])),
    path('variants/', LastBetVariantsView.as_view()),
    path('history/', RoundHistoryView.as_view()),

    path("<int:pk>/stats/", RoundStatsView.as_view()),

    path("<int:pk>/my-variants/", MyVariantsInRoundView.as_view()),

    path('bet/', PlaceBetView.as_view()),

    path('my-win-coupon/', MyWinCouponView.as_view()),

    path('last-results/', TeamStatsView.as_view()),

    path('fan-points/', FanPointsTableView.as_view()),

    path('fan-pool/', FanPoolAmountView.as_view()),

    path("playoff/", include([
        path("vote/", FanVoteView.as_view()),
        path("count/", FanVoteCountView.as_view()),
        path("bracket/", PlayoffBracketView.as_view()),
        path("timer/", NextPlayoffTimerView.as_view()),

    ])),

]
