FROM node:18-alpine

WORKDIR /app

COPY package.json package.json
COPY package-lock.json package-lock.json

COPY .env .env

RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "start"] 