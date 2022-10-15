from waitress import serve
import manage  # main은 flask app을 작성한 py파일입니다.


serve(manage.app, host='0.0.0.0', port=6584)
